import pytest

from mcp_maven_central_search.models import PomDependency
from mcp_maven_central_search.pom import extract_declared_dependencies


def _dep_tuple(d: PomDependency) -> tuple[str, str, str | None, str | None, bool, str | None]:
    return (
        d.group_id,
        d.artifact_id,
        d.version,
        d.scope,
        d.optional,
        d.unresolved_reason,
    )


def test_literal_version_extraction():
    xml = """
    <project>
      <dependencies>
        <dependency>
          <groupId>com.example</groupId>
          <artifactId>lib</artifactId>
          <version>1.2.3</version>
          <scope>compile</scope>
          <optional>false</optional>
        </dependency>
      </dependencies>
    </project>
    """
    deps = extract_declared_dependencies(xml)
    assert len(deps) == 1
    assert _dep_tuple(deps[0]) == (
        "com.example",
        "lib",
        "1.2.3",
        "compile",
        False,
        None,
    )


def test_local_property_resolution():
    xml = """
    <project>
      <properties>
        <guava.version>32.1.0</guava.version>
      </properties>
      <dependencies>
        <dependency>
          <groupId>com.google.guava</groupId>
          <artifactId>guava</artifactId>
          <version>${guava.version}</version>
        </dependency>
      </dependencies>
    </project>
    """
    deps = extract_declared_dependencies(xml)
    assert len(deps) == 1
    assert deps[0].version == "32.1.0"
    assert deps[0].unresolved_reason is None


def test_missing_version_flagged_missing():
    xml = """
    <project>
      <dependencies>
        <dependency>
          <groupId>org.example</groupId>
          <artifactId>no-version</artifactId>
        </dependency>
      </dependencies>
    </project>
    """
    deps = extract_declared_dependencies(xml)
    assert len(deps) == 1
    d = deps[0]
    assert d.version is None
    assert d.unresolved_reason == "missing"


def test_managed_version_flagged_managed():
    xml = """
    <project>
      <dependencyManagement>
        <dependencies>
          <dependency>
            <groupId>org.example</groupId>
            <artifactId>managed-art</artifactId>
            <version>9.9.9</version>
          </dependency>
        </dependencies>
      </dependencyManagement>
      <dependencies>
        <dependency>
          <groupId>org.example</groupId>
          <artifactId>managed-art</artifactId>
        </dependency>
      </dependencies>
    </project>
    """
    deps = extract_declared_dependencies(xml)
    assert len(deps) == 1
    d = deps[0]
    assert d.version is None
    assert d.unresolved_reason == "managed"


def test_unresolved_property_flagged():
    xml = """
    <project>
      <dependencies>
        <dependency>
          <groupId>org.example</groupId>
          <artifactId>ref-prop</artifactId>
          <version>${does.not.exist}</version>
        </dependency>
      </dependencies>
    </project>
    """
    deps = extract_declared_dependencies(xml)
    assert len(deps) == 1
    d = deps[0]
    assert d.version is None
    assert d.unresolved_reason == "property_unresolved"


def test_secure_parser_blocks_xxe():
    # Basic XXE/entity expansion attempt should be blocked by defusedxml
    xml = """
    <!DOCTYPE foo [
      <!ELEMENT foo ANY >
      <!ENTITY xxe SYSTEM "file:///etc/passwd" >]>
    <project>
      <dependencies>
        <dependency>
          <groupId>g</groupId>
          <artifactId>a</artifactId>
          <version>&xxe;</version>
        </dependency>
      </dependencies>
    </project>
    """
    with pytest.raises(Exception):
        extract_declared_dependencies(xml)
