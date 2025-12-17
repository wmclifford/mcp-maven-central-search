"""MCP STDIO server and tool definitions (v1).

Implements PLAN-5.2 (Issue #20): get_latest_version tool.

Design notes:
- Transport adapter stays thin; core logic is kept local and re-usable
  from tests without requiring FastMCP to be importable.
- Caching uses AsyncTTLCache with in-flight de-duplication.
- Logging goes to stderr via the central logging config.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from .cache import AsyncTTLCache, InFlightDeduper
from .central_api import build_params_for_versions, get_client
from .logging_config import configure_logging
from .models import ArtifactVersionInfo, LatestVersionResponse, MavenCoordinate
from .versioning import is_stable, sort_versions

_logger = logging.getLogger(__name__)

# Initialize stderr logging configuration
configure_logging()

# Cache settings (conservative defaults; can be adjusted via settings later)
_CACHE_TTL_SECONDS = 60
_CACHE_MAX_ENTRIES = 256

_versions_cache: AsyncTTLCache[Tuple[str, str, bool], LatestVersionResponse] = AsyncTTLCache(
    default_ttl_seconds=_CACHE_TTL_SECONDS,
    max_entries=_CACHE_MAX_ENTRIES,
)
_deduper: InFlightDeduper[Tuple[str, str, bool], LatestVersionResponse] = InFlightDeduper()


def _filter_versions(versions: list[str], include_prereleases: bool) -> list[str]:
    if include_prereleases:
        return versions
    return [v for v in versions if is_stable(v)]


async def _fetch_versions(group_id: str, artifact_id: str, rows: int) -> list[str]:
    """Query Maven Central for versions list for the given coordinate.

    Uses core=gav with a group/artifact query; returns raw version strings
    as reported by Maven Central.
    """

    client = get_client()
    params = build_params_for_versions(group_id, artifact_id, rows)
    # Only log operation, not full URL + params at info level
    _logger.info("querying maven central versions", extra={"op": "versions", "rows": rows})
    data = await client.get_json(client._base_url, params=params)  # type: ignore[attr-defined]

    # Expected shape per Maven Central: response.docs[] with fields incl. v (version)
    try:
        resp = data.get("response", {})
        docs = resp.get("docs", [])
    except AttributeError:  # pragma: no cover – defensive
        docs = []

    versions: list[str] = []
    for doc in docs:
        v = doc.get("v") if isinstance(doc, dict) else None
        if isinstance(v, str) and v.strip():
            versions.append(v.strip())
    return versions


def _select_latest(versions: list[str]) -> Optional[str]:
    if not versions:
        return None
    ordered = sort_versions(versions)
    return ordered[-1] if ordered else None


async def get_latest_version_core(
    *,
    group_id: str,
    artifact_id: str,
    include_prereleases: bool = False,
    max_versions_to_scan: int = 200,
) -> LatestVersionResponse:
    """Core logic for the get_latest_version tool (transport-neutral).

    Caching key includes prerelease flag to avoid cross-contamination.

    Error handling policy (documented):
    - If Maven Central returns no documents: raise ValueError to be surfaced
      as an MCP tool error by the transport layer.
    - If versions exist but all are filtered out by stability rules: raise
      ValueError with a clear message.
    """

    # Defensive bound on rows
    rows = max(1, min(int(max_versions_to_scan), 500))

    coord = MavenCoordinate(group_id=group_id, artifact_id=artifact_id)
    cache_key = (coord.group_id, coord.artifact_id, bool(include_prereleases))

    cached = await _versions_cache.get(cache_key)
    if cached is not None:
        return cached

    async def _compute() -> LatestVersionResponse:
        all_versions = await _fetch_versions(coord.group_id, coord.artifact_id, rows)
        if not all_versions:
            raise ValueError(
                f"No versions found for coordinate {coord.group_id}:{coord.artifact_id}"
            )

        filtered = _filter_versions(all_versions, include_prereleases)
        if not filtered:
            raise ValueError(
                "All versions are pre-releases; set include_prereleases=True to include them"
            )

        latest_str = _select_latest(filtered)
        latest = ArtifactVersionInfo(version=latest_str) if latest_str else None

        resp = LatestVersionResponse(
            coordinate=coord,
            latest=latest,
            stable_filter_applied=not include_prereleases,
            caveats=[],
        )
        await _versions_cache.set(cache_key, resp)
        return resp

    return await _deduper.run(cache_key, _compute)


# --- Optional FastMCP wiring ---
try:  # Import lazily so unit tests don’t require FastMCP installed
    from fastmcp import FastMCP

    _server = FastMCP("mcp-maven-central-search")

    @_server.tool()
    async def get_latest_version(
        group_id: str,
        artifact_id: str,
        include_prereleases: bool = False,
        max_versions_to_scan: int = 200,
    ) -> dict:
        """Return the latest version for a Maven coordinate.

        This is the MCP-exposed wrapper around the core transport-neutral logic.
        """

        result = await get_latest_version_core(
            group_id=group_id,
            artifact_id=artifact_id,
            include_prereleases=include_prereleases,
            max_versions_to_scan=max_versions_to_scan,
        )
        # Return as plain dict for MCP
        return result.model_dump()

    def run() -> None:  # pragma: no cover
        _server.run()

except Exception:  # FastMCP not installed or unavailable
    # Expose a no-op run to avoid import errors for tests.
    def run() -> None:  # pragma: no cover
        _logger.warning("FastMCP not available; server run() is a no-op", extra={"op": "noop"})


__all__ = [
    "get_latest_version_core",
    "run",
]
