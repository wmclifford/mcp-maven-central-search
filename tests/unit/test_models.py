import pytest

from mcp_maven_central_search.models import (
    ArtifactVersionInfo,
    DeclaredDependenciesResponse,
    LatestVersionResponse,
    MavenCoordinate,
    PomDependency,
    VersionsResponse,
)


def test_maven_coordinate_valid():
    mc = MavenCoordinate(group_id="org.example ", artifact_id=" my-artifact")
    assert mc.group_id == "org.example"
    assert mc.artifact_id == "my-artifact"


@pytest.mark.parametrize(
    "group_id,artifact_id",
    [
        ("", "a"),
        (" ", "a"),
        ("g", ""),
        ("g", " "),
    ],
)
def test_maven_coordinate_invalid_empty(group_id: str, artifact_id: str):
    with pytest.raises(Exception):
        MavenCoordinate(group_id=group_id, artifact_id=artifact_id)


def test_maven_coordinate_length_limit():
    long = "x" * 201
    with pytest.raises(Exception):
        MavenCoordinate(group_id=long, artifact_id="a")
    with pytest.raises(Exception):
        MavenCoordinate(group_id="g", artifact_id=long)


def test_artifact_version_info_valid():
    avi = ArtifactVersionInfo(version="1.2.3")
    assert avi.version == "1.2.3"


def test_pom_dependency_valid_optional_fields():
    dep = PomDependency(
        group_id="org.example",
        artifact_id="lib",
        version=None,
        scope=None,
        optional=True,
        unresolved_reason=None,
    )
    assert dep.optional is True
    assert dep.version is None
    assert dep.scope is None
    assert dep.unresolved_reason is None


def test_pom_dependency_unresolved_reason_enforced():
    # Valid reasons should work
    for reason in ("managed", "property_unresolved", "missing"):
        dep = PomDependency(
            group_id="g",
            artifact_id="a",
            unresolved_reason=reason,
        )
        assert dep.unresolved_reason == reason

    # Invalid reason should raise
    with pytest.raises(Exception):
        PomDependency(group_id="g", artifact_id="a", unresolved_reason="other")


def test_extra_fields_ignored_in_responses():
    coord = {"group_id": "g", "artifact_id": "a", "unknown": 123}
    latest = {
        "version": "1.0.0",
        "timestamp": None,
        "extra": "ignored",
    }
    r1 = LatestVersionResponse(
        coordinate=coord,
        latest=latest,
        stable_filter_applied=True,
        caveats=["note"],
        ignored_field=42,  # type: ignore[arg-type]
    )
    assert r1.coordinate.group_id == "g"
    assert r1.latest and r1.latest.version == "1.0.0"
    assert not hasattr(r1, "ignored_field")

    r2 = VersionsResponse(
        coordinate=coord,
        versions=[latest, {"version": "2.0.0"}],
        extra_top=1,  # type: ignore[arg-type]
    )
    assert len(r2.versions) == 2
    assert r2.versions[0].version == "1.0.0"
    assert not hasattr(r2, "extra_top")

    rd = DeclaredDependenciesResponse(
        coordinate=coord,
        version="1.0.0",
        dependencies=[
            {"group_id": "g", "artifact_id": "a", "optional": False, "x": 1},
        ],
        upstream="ignored",  # type: ignore[arg-type]
    )
    assert rd.version == "1.0.0"
    assert rd.dependencies[0].group_id == "g"
    assert not hasattr(rd, "upstream")
