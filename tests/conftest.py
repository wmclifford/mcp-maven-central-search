from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import respx

from mcp_maven_central_search import server as server_module
from mcp_maven_central_search.config import Settings


@pytest.fixture(autouse=True)
async def _reset_caches() -> AsyncIterator[None]:
    # Ensure isolation across tests by clearing server-level caches
    await server_module._versions_cache.clear()
    await server_module._versions_list_cache.clear()
    await server_module._declared_deps_cache.clear()
    yield


@pytest.fixture
def respx_router() -> Iterator[respx.Router]:
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
def respx_versions_mock(respx_router: respx.Router):
    """Prepare a versions endpoint route on the Maven Central search URL.

    Tests can call `.mock(return_value=...)` and inspect `.called`/`.call_count`.
    """

    base_url = Settings().MAVEN_CENTRAL_BASE_URL
    return respx_router.get(base_url)


@pytest.fixture
def pom_url_builder() -> callable:
    # Helper to construct the canonical POM URL used by download_pom
    from mcp_maven_central_search.pom import _build_pom_url

    def _f(group_id: str, artifact_id: str, version: str) -> str:
        return _build_pom_url(group_id, artifact_id, version)

    return _f
