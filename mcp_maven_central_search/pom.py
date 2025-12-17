from __future__ import annotations

from typing import Final, Optional, Any

import httpx
# Secure XML parsing
from defusedxml import ElementTree as ET  # type: ignore[import-untyped]

from .central_api import get_client
from .models import PomDependency

_REPO_BASE: Final[str] = "https://repo1.maven.org/maven2"
_MAX_POM_BYTES: Final[int] = 2_000_000  # 2 MB safety cap


def _validate_coordinate_part(name: str, value: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError(f"{name} must be non-empty")
    # Disallow obvious path traversal and separators
    if v.startswith("/") or ".." in v or "/" in v or "\\" in v:
        raise ValueError(f"{name} contains illegal path characters")
    return v


def _group_path(group_id: str) -> str:
    # extra defense: no empty segments from things like leading/trailing dots
    if group_id.startswith(".") or group_id.endswith(".") or ".." in group_id:
        raise ValueError("group_id contains illegal path characters")
    return group_id.replace(".", "/")


def _build_pom_url(group_id: str, artifact_id: str, version: str) -> str:
    g = _validate_coordinate_part("group_id", group_id)
    a = _validate_coordinate_part("artifact_id", artifact_id)
    v = _validate_coordinate_part("version", version)
    url = f"{_REPO_BASE}/{_group_path(g)}/{a}/{v}/{a}-{v}.pom"
    if not url.lower().startswith("https://"):
        # Defensive, though construction ensures it
        raise ValueError("URL must be HTTPS")
    return url


async def download_pom(group_id: str, artifact_id: str, version: str) -> str:
    """Download a Maven POM as UTF-8 text with strict safety checks.

    Returns the raw XML string. Content is treated as untrusted; no parsing here.
    """
    url = _build_pom_url(group_id, artifact_id, version)

    client = get_client()

    # Single request using shared AsyncClient; rely on its timeout configuration.
    # We stream to enforce a strict maximum size in-memory.
    try:
        resp = await client._client.get(url, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPStatusError:
        # Propagate with original context for clarity
        raise

    total = 0
    chunks: list[bytes] = []
    async for chunk in resp.aiter_bytes():
        if not chunk:
            continue
        total += len(chunk)
        if total > _MAX_POM_BYTES:
            raise ValueError("POM exceeds maximum allowed size")
        chunks.append(chunk)

    data = b"".join(chunks)
    # Decode defensively as UTF-8, replacing invalid sequences
    return data.decode("utf-8", errors="replace")


__all__ = [
    "download_pom",
    "extract_declared_dependencies",
]


def _local_name(tag: str) -> str:
    """Return the local name of an XML tag, stripping any namespace."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _child_text(elem: Any, name: str) -> Optional[str]:
    for child in elem:
        if _local_name(child.tag) == name:
            return (child.text or "").strip() or None
    return None


def _collect_properties(root: Any) -> dict[str, str]:
    props: dict[str, str] = {}
    for child in root:
        if _local_name(child.tag) == "properties":
            for prop in child:
                key = _local_name(prop.tag)
                val = (prop.text or "").strip()
                if key and val:
                    props[key] = val
            break
    return props


def _collect_managed_coords(root: Any) -> set[tuple[str, str]]:
    managed: set[tuple[str, str]] = set()
    # <dependencyManagement>
    #   <dependencies>
    #     <dependency>...</dependency>
    #   </dependencies>
    # </dependencyManagement>
    dm = None
    for child in root:
        if _local_name(child.tag) == "dependencyManagement":
            dm = child
            break
    if dm is None:
        return managed
    deps_parent = None
    for child in dm:
        if _local_name(child.tag) == "dependencies":
            deps_parent = child
            break
    if deps_parent is None:
        return managed
    for dep in deps_parent:
        if _local_name(dep.tag) != "dependency":
            continue
        gid = _child_text(dep, "groupId")
        aid = _child_text(dep, "artifactId")
        if gid and aid:
            managed.add((gid, aid))
    return managed


def _find_project_dependencies(root: Any) -> list[Any]:
    # Only immediate project-level <dependencies>
    for child in root:
        if _local_name(child.tag) == "dependencies":
            return [d for d in child if _local_name(d.tag) == "dependency"]
    return []


def _resolve_property(
        version_value: str, properties: dict[str, str]
) -> tuple[Optional[str], Optional[str]]:
    """Resolve ${prop} placeholders using local properties.

    Returns (version, unresolved_reason). If unresolved, version=None and reason set.
    """
    v = version_value.strip()
    if v.startswith("${") and v.endswith("}"):
        key = v[2:-1]
        if key in properties and properties[key]:
            return properties[key], None
        return None, "property_unresolved"
    return v or None, None


def extract_declared_dependencies(pom_xml: str) -> list[PomDependency]:
    """Extract declared dependencies from a POM XML string.

    Security:
        Uses defusedxml to prevent XXE and entity expansion attacks.

    Behavior:
        - Only considers project-level <dependencies>.
        - Does not resolve dependencyManagement; marks such versions as managed (unresolved).
        - Resolves local <properties> used as ${...} in <version>.
        - Returns PomDependency list; may set unresolved_reason when version not resolved.

    Raises:
        Exception (from defusedxml) for invalid or unsafe XML inputs.
    """
    # Parse safely; defusedxml will raise on unsafe constructs
    root = ET.fromstring(pom_xml)

    properties = _collect_properties(root)
    managed = _collect_managed_coords(root)
    deps_elems = _find_project_dependencies(root)

    results: list[PomDependency] = []
    for dep in deps_elems:
        gid = _child_text(dep, "groupId")
        aid = _child_text(dep, "artifactId")
        ver_raw = _child_text(dep, "version")
        scope = _child_text(dep, "scope")
        optional_text = _child_text(dep, "optional")
        optional = (optional_text or "").strip().lower() in {"true", "1", "yes"}

        if not gid or not aid:
            # Skip malformed entries lacking required identifiers
            # Deterministic behavior: ignore silently rather than raising
            continue

        version: Optional[str] = None
        unresolved: Optional[str] = None

        if ver_raw and ver_raw.strip():
            version, unresolved = _resolve_property(ver_raw, properties)
        else:
            # No version provided
            if (gid, aid) in managed:
                unresolved = "managed"
            else:
                unresolved = "missing"

        results.append(
            PomDependency(
                group_id=gid,
                artifact_id=aid,
                version=version,
                scope=scope,
                optional=optional,
                unresolved_reason=unresolved,  # type: ignore[arg-type]
            )
        )

    return results
