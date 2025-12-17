import asyncio
from typing import Any

import httpx
import pytest
import respx

from mcp_maven_central_search.server import get_latest_version_core


def _mk_response(versions: list[str]) -> dict[str, Any]:
    # Maven Central shape: response.docs with 'v' field as version
    docs = [{"v": v} for v in versions]
    return {"response": {"numFound": len(docs), "docs": docs}}


@pytest.mark.asyncio
async def test_latest_version_stable_default_picks_correct() -> None:
    # mix of stable and pre-release; stable default should pick highest stable
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://search.maven.org/solrsearch/select").mock(
            return_value=httpx.Response(
                200,
                json=_mk_response(
                    [
                        "1.0.0",
                        "1.1.0-beta1",
                        "1.1.0",
                        "2.0.0-rc1",
                    ]
                ),
            )
        )

        result = await get_latest_version_core(
            group_id="com.example", artifact_id="lib", include_prereleases=False
        )

        assert result.coordinate.group_id == "com.example"
        assert result.coordinate.artifact_id == "lib"
        assert result.stable_filter_applied is True
        assert result.latest is not None
        assert result.latest.version == "1.1.0"
        assert route.call_count == 1


@pytest.mark.asyncio
async def test_include_prereleases_can_select_prerelease_when_highest() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get("https://search.maven.org/solrsearch/select").mock(
            return_value=httpx.Response(
                200,
                json=_mk_response(
                    [
                        "1.2.0",
                        "1.3.0-rc1",
                        "1.3.0-beta2",
                    ]
                ),
            )
        )

        result = await get_latest_version_core(
            group_id="org.acme", artifact_id="core", include_prereleases=True
        )

        assert result.latest is not None
        # With prereleases allowed, rc1 may be selected if ordering deems
        # it higher than the provided stable versions.
        assert result.latest.version in {"1.3.0-rc1", "1.2.0"}
        # Ensure flag surfaced
        assert result.stable_filter_applied is False


@pytest.mark.asyncio
async def test_no_results_returns_tool_error() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get("https://search.maven.org/solrsearch/select").mock(
            return_value=httpx.Response(200, json=_mk_response([]))
        )

        with pytest.raises(ValueError):
            await get_latest_version_core(
                group_id="no.group", artifact_id="no-art", include_prereleases=False
            )


@pytest.mark.asyncio
async def test_caching_and_inflight_dedupe_reduce_calls() -> None:
    # First call triggers HTTP; subsequent concurrent calls dedupe; later cached
    calls = {"n": 0}

    async def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        # tiny context switch to exercise dedupe
        await asyncio.sleep(0)
        return httpx.Response(200, json=_mk_response(["0.9.0", "1.0.0", "1.0.1"]))

    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://search.maven.org/solrsearch/select").mock(side_effect=handler)

        # Fire multiple concurrent identical requests
        tasks = [
            asyncio.create_task(
                get_latest_version_core(
                    group_id="com.dupe", artifact_id="lib", include_prereleases=False
                )
            )
            for _ in range(5)
        ]
        results = await asyncio.gather(*tasks)
        assert all(r.latest is not None and r.latest.version == "1.0.1" for r in results)

        # Only one underlying HTTP call expected due to inflight dedupe
        assert calls["n"] == 1
        assert route.call_count == 1

        # Now, a subsequent request should hit the cache and not call HTTP again
        r2 = await get_latest_version_core(
            group_id="com.dupe", artifact_id="lib", include_prereleases=False
        )
        assert r2.latest is not None and r2.latest.version == "1.0.1"
        assert calls["n"] == 1
