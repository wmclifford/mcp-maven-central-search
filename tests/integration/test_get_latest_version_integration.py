import httpx
import pytest

from mcp_maven_central_search.server import get_latest_version_core


@pytest.mark.asyncio
async def test_get_latest_version_filters_prereleases_and_uses_cache(respx_versions_mock):
    # Arrange: mock Maven Central versions response with mixed stable/prerelease
    group = "com.acme"
    artifact = "demo"

    # First call returns data; any further calls should not be made due to cache/dedup
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

    route = respx_versions_mock.mock(return_value=httpx.Response(200, json=response_json))

    # Act: first call should hit HTTP
    result1 = await get_latest_version_core(group_id=group, artifact_id=artifact)
    # Second call with same params should be served from cache (no new HTTP)
    result2 = await get_latest_version_core(group_id=group, artifact_id=artifact)

    # Assert: prereleases excluded; highest stable is 2.1.0
    assert result1.latest is not None
    assert result1.latest.version == "2.1.0"
    assert result1.stable_filter_applied is True

    # Cache should return identical payload
    assert result2.model_dump() == result1.model_dump()

    # Only a single underlying HTTP request was made
    assert route.called
    assert route.call_count == 1
