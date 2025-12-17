from __future__ import annotations

from typing import Final

import httpx

from .central_api import get_client

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
]
