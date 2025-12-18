import httpx
import pytest
import respx

from mcp_maven_central_search.server import get_declared_dependencies_core

POM_XML = """
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>demo</artifactId>
  <version>1.0.0</version>
  <properties>
    <junit.version>5.10.1</junit.version>
  </properties>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>org.managed</groupId>
        <artifactId>managed-lib</artifactId>
        <version>9.9.9</version>
      </dependency>
    </dependencies>
  </dependencyManagement>
  <dependencies>
    <!-- No scope, no version but managed elsewhere (unresolved: managed) -->
    <dependency>
      <groupId>org.managed</groupId>
      <artifactId>managed-lib</artifactId>
    </dependency>

    <!-- Compile scope implied; optional false (default); property version resolved -->
    <dependency>
      <groupId>org.junit</groupId>
      <artifactId>junit-jupiter</artifactId>
      <version>${junit.version}</version>
    </dependency>

    <!-- Explicit runtime scope -->
    <dependency>
      <groupId>org.slf4j</groupId>
      <artifactId>slf4j-api</artifactId>
      <version>2.0.13</version>
      <scope>runtime</scope>
    </dependency>

    <!-- Optional true with test scope -->
    <dependency>
      <groupId>org.mockito</groupId>
      <artifactId>mockito-core</artifactId>
      <version>5.12.0</version>
      <scope>test</scope>
      <optional>true</optional>
    </dependency>

    <!-- Missing version and not managed (unresolved: missing) -->
    <dependency>
      <groupId>org.unversioned</groupId>
      <artifactId>lib</artifactId>
    </dependency>
  </dependencies>
</project>
"""


def _pom_url(group: str, artifact: str, version: str) -> str:
    base = "https://repo1.maven.org/maven2"
    path = f"{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}.pom"
    return f"{base}/{path}"


@pytest.mark.asyncio
async def test_basic_extraction_and_sorting() -> None:
    url = _pom_url("com.example", "demo", "1.0.0")
    with respx.mock(assert_all_called=True) as router:
        router.get(url).mock(return_value=httpx.Response(200, content=POM_XML.encode("utf-8")))
        resp = await get_declared_dependencies_core(
            group_id="com.example",
            artifact_id="demo",
            version="1.0.0",
        )

    deps = resp.dependencies
    # Ensure stable sort by (group_id, artifact_id, version or "")
    keys = [(d.group_id, d.artifact_id, d.version or "") for d in deps]
    assert keys == sorted(keys)

    # Basic sanity: presence of specific entries and unresolved reasons
    # managed-lib: unresolved managed
    managed = next(
        d for d in deps if d.group_id == "org.managed" and d.artifact_id == "managed-lib"
    )
    assert managed.version is None and managed.unresolved_reason == "managed"

    junit = next(d for d in deps if d.group_id == "org.junit" and d.artifact_id == "junit-jupiter")
    assert junit.version == "5.10.1" and junit.scope is None and not junit.optional

    unv = next(d for d in deps if d.group_id == "org.unversioned" and d.artifact_id == "lib")
    assert unv.version is None and unv.unresolved_reason == "missing"


@pytest.mark.asyncio
async def test_include_optional_false_filters_optional() -> None:
    url = _pom_url("com.example", "demo", "1.0.0")
    with respx.mock(assert_all_called=True) as router:
        router.get(url).mock(return_value=httpx.Response(200, content=POM_XML.encode("utf-8")))
        resp = await get_declared_dependencies_core(
            group_id="com.example",
            artifact_id="demo",
            version="1.0.0",
            include_optional=False,
        )

    # Ensure optional dependency is filtered out
    assert all(not d.optional for d in resp.dependencies)
    assert not any(d.group_id == "org.mockito" for d in resp.dependencies)


@pytest.mark.asyncio
async def test_include_scopes_filters_and_treats_none_as_compile() -> None:
    url = _pom_url("com.example", "demo", "1.0.0")
    with respx.mock(assert_all_called=True) as router:
        router.get(url).mock(return_value=httpx.Response(200, content=POM_XML.encode("utf-8")))
        # Only runtime deps
        resp_runtime = await get_declared_dependencies_core(
            group_id="com.example",
            artifact_id="demo",
            version="1.0.0",
            include_scopes=["runtime"],
        )
        assert all((d.scope or "runtime").lower() == "runtime" for d in resp_runtime.dependencies)

        # Treat None scope as compile
        resp_compile = await get_declared_dependencies_core(
            group_id="com.example",
            artifact_id="demo",
            version="1.0.0",
            include_scopes=["compile"],
        )
        assert any(
            d.group_id == "org.junit" for d in resp_compile.dependencies
        )  # junit has no scope -> compile
        # Ensure runtime dep excluded when only compile
        assert not any(
            d.group_id == "org.slf4j" and d.scope == "runtime" for d in resp_compile.dependencies
        )


@pytest.mark.asyncio
async def test_404_returns_tool_error() -> None:
    url = _pom_url("com.missing", "lib", "0.0.1")
    with respx.mock(assert_all_called=True) as router:
        router.get(url).mock(return_value=httpx.Response(404, text="not found"))
        with pytest.raises(ValueError):
            await get_declared_dependencies_core(
                group_id="com.missing",
                artifact_id="lib",
                version="0.0.1",
            )


@pytest.mark.asyncio
async def test_invalid_xml_returns_tool_error() -> None:
    url = _pom_url("com.bad", "lib", "1.2.3")
    with respx.mock(assert_all_called=True) as router:
        router.get(url).mock(return_value=httpx.Response(200, content=b"<project>"))
        with pytest.raises(ValueError):
            await get_declared_dependencies_core(
                group_id="com.bad",
                artifact_id="lib",
                version="1.2.3",
            )


@pytest.mark.asyncio
async def test_caching_dedupes_subsequent_calls() -> None:
    url = _pom_url("com.cache", "lib", "1.0.0")
    with respx.mock(assert_all_called=True) as router:
        route = router.get(url).mock(
            return_value=httpx.Response(200, content=POM_XML.encode("utf-8"))
        )
        # first call hits network
        resp1 = await get_declared_dependencies_core(
            group_id="com.cache",
            artifact_id="lib",
            version="1.0.0",
        )
        assert resp1.dependencies
        # second call should be served from cache
        resp2 = await get_declared_dependencies_core(
            group_id="com.cache",
            artifact_id="lib",
            version="1.0.0",
        )
        assert resp2.dependencies
        assert route.called and route.call_count == 1
