import asyncio

import httpx
import pytest
import respx

from mcp_maven_central_search.central_api import build_params_for_versions
from mcp_maven_central_search.config import Settings
from mcp_maven_central_search.server import get_versions_core


def _make_response(versions: list[str]) -> dict:
    return {
        "response": {
            "docs": [{"v": v} for v in versions],
        }
    }


@pytest.mark.asyncio
async def test_stable_only_excludes_prereleases() -> None:
    group = "com.example"
    artifact = "demo"
    params = build_params_for_versions(group, artifact, 200)
    base_url = Settings().MAVEN_CENTRAL_BASE_URL

    versions = [
        "1.0.0",
        "1.1.0-beta1",
        "1.0.1",
        "2.0.0-SNAPSHOT",
    ]

    with respx.mock(assert_all_called=True) as router:
        route = router.get(base_url, params={k: str(v) for k, v in params.items()}).mock(
            return_value=httpx.Response(200, json=_make_response(versions))
        )
        resp = await get_versions_core(
            group_id=group, artifact_id=artifact, include_prereleases=False, max_versions=200
        )
        assert resp.coordinate.group_id == group
        assert resp.coordinate.artifact_id == artifact
        # Should exclude prereleases and be ordered highest→lowest
        assert [v.version for v in resp.versions] == ["1.0.1", "1.0.0"]
        assert resp.stable_filter_applied is True
        assert route.called


@pytest.mark.asyncio
async def test_include_prereleases_true_includes() -> None:
    group = "com.example"
    artifact = "demo"
    params = build_params_for_versions(group, artifact, 200)
    base_url = Settings().MAVEN_CENTRAL_BASE_URL

    versions = [
        "1.0.0",
        "1.1.0-beta1",
        "1.0.1",
        "2.0.0-SNAPSHOT",
    ]

    with respx.mock(assert_all_called=True) as router:
        route = router.get(base_url, params={k: str(v) for k, v in params.items()}).mock(
            return_value=httpx.Response(200, json=_make_response(versions))
        )
        resp = await get_versions_core(
            group_id=group, artifact_id=artifact, include_prereleases=True, max_versions=200
        )
        # Highest→lowest ordering with prereleases included
        assert [v.version for v in resp.versions] == [
            "2.0.0-SNAPSHOT",
            "1.1.0-beta1",
            "1.0.1",
            "1.0.0",
        ]
        assert resp.stable_filter_applied is False
        assert route.called


@pytest.mark.asyncio
async def test_empty_results_raises_error() -> None:
    group = "org.none"
    artifact = "missing"
    params = build_params_for_versions(group, artifact, 50)
    base_url = Settings().MAVEN_CENTRAL_BASE_URL

    with respx.mock(assert_all_called=True) as router:
        router.get(base_url, params={k: str(v) for k, v in params.items()}).mock(
            return_value=httpx.Response(200, json=_make_response([]))
        )
        with pytest.raises(ValueError):
            await get_versions_core(
                group_id=group, artifact_id=artifact, include_prereleases=False, max_versions=50
            )


@pytest.mark.asyncio
async def test_ordering_descending_high_to_low() -> None:
    group = "com.acme"
    artifact = "lib"
    params = build_params_for_versions(group, artifact, 10)
    base_url = Settings().MAVEN_CENTRAL_BASE_URL

    versions = ["1.0", "1.0.1", "1.0.Final", "0.9", "2.0-rc1", "2.0"]

    with respx.mock(assert_all_called=True) as router:
        router.get(base_url, params={k: str(v) for k, v in params.items()}).mock(
            return_value=httpx.Response(200, json=_make_response(versions))
        )
        resp = await get_versions_core(
            group_id=group, artifact_id=artifact, include_prereleases=True, max_versions=10
        )
        # Expect 2.0 > 2.0-rc1 > 1.0.1 > 1.0.Final (==1.0) > 1.0 > 0.9
        assert [v.version for v in resp.versions] == [
            "2.0",
            "2.0-rc1",
            "1.0.1",
            "1.0.Final",
            "1.0",
            "0.9",
        ]


@pytest.mark.asyncio
async def test_cache_and_dedupe_reduce_duplicate_calls() -> None:
    group = "com.example"
    artifact = "dedupe"
    params = build_params_for_versions(group, artifact, 100)
    base_url = Settings().MAVEN_CENTRAL_BASE_URL

    versions = ["1.0", "1.1", "1.2"]

    with respx.mock(assert_all_called=True) as router:
        route = router.get(base_url, params={k: str(v) for k, v in params.items()}).mock(
            return_value=httpx.Response(200, json=_make_response(versions))
        )

        # Fire two concurrent requests with the same key; should result in a single GET
        r1, r2 = await asyncio.gather(
            get_versions_core(
                group_id=group,
                artifact_id=artifact,
                include_prereleases=False,
                max_versions=100,
            ),
            get_versions_core(
                group_id=group,
                artifact_id=artifact,
                include_prereleases=False,
                max_versions=100,
            ),
        )

        assert [v.version for v in r1.versions] == ["1.2", "1.1", "1.0"]
        assert [v.version for v in r2.versions] == ["1.2", "1.1", "1.0"]
        # One underlying HTTP call due to in-flight deduplication
        assert route.call_count == 1
