import httpx
import pytest

from mcp_maven_central_search.server import get_versions_core


@pytest.mark.asyncio
async def test_get_versions_default_stable_only_descending(respx_versions_mock):
    group = "com.acme"
    artifact = "demo"

    response_json = {
        "response": {
            "docs": [
                {"v": "1.0.0"},
                {"v": "1.1.0"},
                {"v": "2.0.0-alpha"},
                {"v": "2.0.0"},
                {"v": "2.1.0-beta.1"},
                {"v": "2.1.0"},
            ]
        }
    }

    respx_versions_mock.mock(return_value=httpx.Response(200, json=response_json))

    result = await get_versions_core(group_id=group, artifact_id=artifact)

    # Should exclude prereleases and be ordered highest -> lowest
    versions = [v.version for v in result.versions]
    assert versions == ["2.1.0", "2.0.0", "1.1.0", "1.0.0"]
    assert result.stable_filter_applied is True


@pytest.mark.asyncio
async def test_get_versions_include_prereleases(respx_versions_mock):
    group = "com.acme"
    artifact = "demo"

    response_json = {
        "response": {
            "docs": [
                {"v": "1.0.0"},
                {"v": "1.1.0"},
                {"v": "2.0.0-alpha"},
                {"v": "2.0.0"},
                {"v": "2.1.0-beta.1"},
                {"v": "2.1.0"},
            ]
        }
    }

    respx_versions_mock.mock(return_value=httpx.Response(200, json=response_json))

    result = await get_versions_core(group_id=group, artifact_id=artifact, include_prereleases=True)

    # With prereleases: include all, ordered highest -> lowest
    versions = [v.version for v in result.versions]
    assert versions == [
        "2.1.0",
        "2.1.0-beta.1",
        "2.0.0",
        "2.0.0-alpha",
        "1.1.0",
        "1.0.0",
    ]
    assert result.stable_filter_applied is False
