import httpx
import pytest

from mcp_maven_central_search.server import get_declared_dependencies_core

POM_XML = """
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.acme</groupId>
  <artifactId>demo</artifactId>
  <version>1.0.0</version>
  <dependencies>
    <dependency>
      <groupId>org.foo</groupId>
      <artifactId>core</artifactId>
      <version>1.2.3</version>
      <!-- no scope -> treated as compile -->
    </dependency>
    <dependency>
      <groupId>org.foo</groupId>
      <artifactId>optional-lib</artifactId>
      <version>2.0.0</version>
      <optional>true</optional>
      <scope>runtime</scope>
    </dependency>
    <dependency>
      <groupId>org.bar</groupId>
      <artifactId>testkit</artifactId>
      <version>0.9.0</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>org.bom</groupId>
        <artifactId>managed</artifactId>
        <version>1.0.0</version>
      </dependency>
    </dependencies>
  </dependencyManagement>
  <properties>
    <prop.version>3.4.5</prop.version>
  </properties>
</project>
"""


@pytest.mark.asyncio
async def test_declared_dependencies_extraction_and_filters(respx_router, pom_url_builder):
    group = "com.acme"
    artifact = "demo"
    version = "1.0.0"
    url = pom_url_builder(group, artifact, version)

    respx_router.get(url).mock(return_value=httpx.Response(200, content=POM_XML.encode("utf-8")))

    # Default: include_optional=True, include_scopes=None -> all deps included
    resp_all = await get_declared_dependencies_core(
        group_id=group, artifact_id=artifact, version=version
    )

    names_all = [
        (d.group_id, d.artifact_id, d.scope or None, d.optional) for d in resp_all.dependencies
    ]
    assert ("org.foo", "core", None, False) in names_all  # missing scope preserved as None
    assert ("org.foo", "optional-lib", "runtime", True) in names_all
    assert ("org.bar", "testkit", "test", False) in names_all

    # Exclude optional dependencies
    resp_no_opt = await get_declared_dependencies_core(
        group_id=group, artifact_id=artifact, version=version, include_optional=False
    )
    names_no_opt = {(d.group_id, d.artifact_id) for d in resp_no_opt.dependencies}
    assert ("org.foo", "optional-lib") not in names_no_opt

    # Scope filtering: treat missing scope as 'compile'. Include only compile
    resp_compile_only = await get_declared_dependencies_core(
        group_id=group,
        artifact_id=artifact,
        version=version,
        include_scopes=["compile"],
    )
    scopes = {
        (d.group_id, d.artifact_id, (d.scope or "compile")) for d in resp_compile_only.dependencies
    }
    # core has missing scope -> treated as compile and should be included
    assert ("org.foo", "core", "compile") in scopes
    # runtime/test should be excluded
    assert not any(ga for ga in scopes if ga[1] in {"optional-lib", "testkit"})
