"""MCP STDIO server and tool definitions (v1).

Implements PLAN-5.2 (Issue #20): get_latest_version tool.

Design notes:
- Transport adapter stays thin; core logic is kept local and re-usable.
- Caching uses AsyncTTLCache with in-flight de-duplication.
- Logging goes to stderr via the central logging config.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import httpx
from fastmcp import FastMCP

from .cache import AsyncTTLCache, InFlightDeduper
from .central_api import build_params_for_versions, get_client
from .config import Settings
from .logging_config import configure_logging
from .models import (
    ArtifactVersionInfo,
    DeclaredDependenciesResponse,
    LatestVersionResponse,
    MavenCoordinate,
    PomDependency,
    VersionsResponse,
)
from .pom import download_pom, extract_declared_dependencies
from .versioning import is_stable, sort_versions

_logger = logging.getLogger(__name__)

# Initialize stderr logging configuration
configure_logging()

# Cache settings (conservative defaults; can be adjusted via settings later)
_CACHE_TTL_SECONDS = 60
_CACHE_MAX_ENTRIES = 256

_versions_cache: AsyncTTLCache[Tuple[str, str, bool, int], LatestVersionResponse] = AsyncTTLCache(
    default_ttl_seconds=_CACHE_TTL_SECONDS,
    max_entries=_CACHE_MAX_ENTRIES,
)
_deduper: InFlightDeduper[Tuple[str, str, bool, int], LatestVersionResponse] = InFlightDeduper()

# Separate cache for full versions listing responses (PLAN-5.3)
_versions_list_cache: AsyncTTLCache[Tuple[str, str, bool, int], VersionsResponse] = AsyncTTLCache(
    default_ttl_seconds=_CACHE_TTL_SECONDS,
    max_entries=_CACHE_MAX_ENTRIES,
)
_versions_list_deduper: InFlightDeduper[Tuple[str, str, bool, int], VersionsResponse] = (
    InFlightDeduper()
)

# Cache for declared dependencies (PLAN-5.4)
_declared_deps_cache: AsyncTTLCache[
    Tuple[str, str, str, bool, Tuple[str, ...]], DeclaredDependenciesResponse
] = AsyncTTLCache(
    default_ttl_seconds=_CACHE_TTL_SECONDS,
    max_entries=_CACHE_MAX_ENTRIES,
)
_declared_deps_deduper: InFlightDeduper[
    Tuple[str, str, str, bool, Tuple[str, ...]], DeclaredDependenciesResponse
] = InFlightDeduper()


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
    params_mixed = build_params_for_versions(group_id, artifact_id, rows)
    # Only log operation, not full URL + params at info level
    _logger.info("querying maven central versions", extra={"op": "versions", "rows": rows})
    # Avoid reaching into client private attributes; use configured Settings
    base_url = Settings().MAVEN_CENTRAL_BASE_URL
    # get_json expects Dict[str, str]; convert any int values to str for type safety
    params: dict[str, str] = {k: str(v) for k, v in params_mixed.items()}
    data = await client.get_json(base_url, params=params)

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
    # Include the effective row limit in the cache key to avoid cross-contamination
    cache_key = (coord.group_id, coord.artifact_id, bool(include_prereleases), rows)

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


async def get_versions_core(
    *,
    group_id: str,
    artifact_id: str,
    include_prereleases: bool = False,
    max_versions: int = 200,
) -> VersionsResponse:
    """Core logic for the get_versions tool (transport-neutral).

    Behavior per PLAN-5.3:
    - Query Maven Central for versions for g:a
    - Apply stability filtering unless include_prereleases is True
    - Order versions using sort_versions, then return highest→lowest
    - Enforce an upper bound on the number of versions retrieved/surfaced

    Errors:
    - If Maven Central returns no results, raise ValueError with a clear message.
    - If versions exist but all filtered out (when include_prereleases is False),
      return an empty list? Spec mirrors latest tool error; keep consistent and raise.
    """

    # Defensive clamp; do not allow unbounded requests upstream
    rows = max(1, min(int(max_versions), 500))

    coord = MavenCoordinate(group_id=group_id, artifact_id=artifact_id)
    cache_key = (coord.group_id, coord.artifact_id, bool(include_prereleases), rows)

    cached = await _versions_list_cache.get(cache_key)
    if cached is not None:
        return cached

    async def _compute() -> VersionsResponse:
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

        ordered_low_to_high = sort_versions(filtered)
        ordered_high_to_low = list(reversed(ordered_low_to_high))
        infos = [ArtifactVersionInfo(version=v) for v in ordered_high_to_low[:rows]]

        resp = VersionsResponse(
            coordinate=coord,
            versions=infos,
            stable_filter_applied=not include_prereleases,
            caveats=[],
        )
        await _versions_list_cache.set(cache_key, resp)
        return resp

    return await _versions_list_deduper.run(cache_key, _compute)


_server = FastMCP("mcp-maven-central-search")


def _normalize_scopes(scopes: Optional[list[str]]) -> Tuple[str, ...]:
    """Normalize scopes list for deterministic behavior and cache key.

    - None -> empty tuple (means include all scopes)
    - Lowercase, strip, unique, sorted.
    """
    if not scopes:
        return tuple()
    norm = sorted({(s or "").strip().lower() for s in scopes if (s or "").strip()})
    return tuple(norm)


def _dep_sort_key(dep: PomDependency) -> Tuple[str, str, str]:
    # Stable ordering: by (group_id, artifact_id, version or "")
    return (dep.group_id, dep.artifact_id, dep.version or "")


def _scope_for_filtering(scope: Optional[str]) -> str:
    """Treat missing scope as 'compile' when filtering per PLAN-5.4."""
    return (scope or "compile").strip().lower() or "compile"


async def get_declared_dependencies_core(
    *,
    group_id: str,
    artifact_id: str,
    version: str,
    include_optional: bool = True,
    include_scopes: Optional[list[str]] = None,
) -> DeclaredDependenciesResponse:
    """Core logic for PLAN-5.4: declared dependencies for a specific version.

    - Downloads the POM, parses declared dependencies.
    - Applies optional filtering by 'optional' flag and scopes.
    - Deterministically sorts results.
    - Caches by (g,a,v, include_optional, normalized_scopes).
    """

    coord = MavenCoordinate(group_id=group_id, artifact_id=artifact_id)
    scopes_key = _normalize_scopes(include_scopes)
    cache_key = (coord.group_id, coord.artifact_id, version, bool(include_optional), scopes_key)

    cached = await _declared_deps_cache.get(cache_key)
    if cached is not None:
        return cached

    async def _compute() -> DeclaredDependenciesResponse:
        # Download POM
        try:
            _logger.info(
                "downloading POM for declared dependencies",
                extra={
                    "op": "get_declared_dependencies",
                    "group_id": coord.group_id,
                    "artifact_id": coord.artifact_id,
                },
            )
            pom_xml = await download_pom(coord.group_id, coord.artifact_id, version)
        except httpx.HTTPStatusError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 404:
                raise ValueError(
                    f"POM not found for {coord.group_id}:{coord.artifact_id}:{version}"
                )
            # surface a generic message for other HTTP errors
            raise ValueError(
                f"Failed to download POM (status={status}) for "
                f"{coord.group_id}:{coord.artifact_id}:{version}"
            )
        except Exception as e:
            # Other download errors
            raise ValueError(f"Failed to download POM: {e}")

        # Parse dependencies
        try:
            deps = extract_declared_dependencies(pom_xml)
        except Exception:
            raise ValueError("Invalid POM XML")

        # Filtering: include_optional flag
        if not include_optional:
            deps = [d for d in deps if not d.optional]

        # Filtering: include_scopes if provided
        if scopes_key:
            allowed = set(scopes_key)
            deps = [d for d in deps if _scope_for_filtering(d.scope) in allowed]

        # Stable ordering
        deps_sorted = sorted(deps, key=_dep_sort_key)

        resp = DeclaredDependenciesResponse(
            coordinate=coord,
            version=version,
            dependencies=deps_sorted,
            caveats=[],
        )
        await _declared_deps_cache.set(cache_key, resp)
        return resp

    return await _declared_deps_deduper.run(cache_key, _compute)


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


@_server.tool()
async def get_versions(
    group_id: str,
    artifact_id: str,
    include_prereleases: bool = False,
    max_versions: int = 200,
) -> dict:
    """Return a sorted list of versions (highest → lowest) for a coordinate.

    Transport wrapper around get_versions_core.
    """

    result = await get_versions_core(
        group_id=group_id,
        artifact_id=artifact_id,
        include_prereleases=include_prereleases,
        max_versions=max_versions,
    )
    return result.model_dump()


@_server.tool()
async def get_declared_dependencies(
    group_id: str,
    artifact_id: str,
    version: str,
    include_optional: bool = True,
    include_scopes: Optional[list[str]] = None,
) -> dict:
    """Return declared dependencies for the given coordinate and version.

    Transport wrapper around get_declared_dependencies_core.
    """

    result = await get_declared_dependencies_core(
        group_id=group_id,
        artifact_id=artifact_id,
        version=version,
        include_optional=include_optional,
        include_scopes=include_scopes,
    )
    return result.model_dump()


def run() -> None:  # pragma: no cover
    _server.run()


__all__ = [
    "get_latest_version_core",
    "get_versions_core",
    "get_declared_dependencies_core",
    "run",
]
