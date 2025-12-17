"""Pydantic domain and response models.

These models are intentionally small, explicit, and validation-focused. They
model only what is needed for v1 (PLAN-1.3) and avoid embedding business
logic. Unknown/extra fields from upstream APIs are tolerated and ignored.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Reasonable maximum length for Maven coordinate parts. Maven Central examples
# are typically < 100 chars; we pick 200 as a conservative, documented limit.
_COORD_PART_MAX_LEN = 200


class MavenCoordinate(BaseModel):
    """Represents a Maven coordinate (groupId:artifactId).

    Packaging/classifier are out of scope for v1 (see Locked Decisions).
    """

    model_config = ConfigDict(extra="ignore")

    group_id: str = Field(..., min_length=1, max_length=_COORD_PART_MAX_LEN)
    artifact_id: str = Field(..., min_length=1, max_length=_COORD_PART_MAX_LEN)

    @field_validator("group_id", "artifact_id")
    @classmethod
    def _strip_and_validate(cls, v: str) -> str:
        # Disallow purely whitespace values and enforce trimmed storage
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("must not be empty")
        return v_stripped


class ArtifactVersionInfo(BaseModel):
    """Version and optional timestamp metadata for an artifact."""

    model_config = ConfigDict(extra="ignore")

    version: str = Field(..., min_length=1)
    timestamp: Optional[datetime] = None


class PomDependency(BaseModel):
    """Represents a declared dependency entry from a POM.

    `unresolved_reason` documents why a version could not be resolved when
    parsing the POM without full dependency management:
      - managed
      - property_unresolved
      - missing
    """

    model_config = ConfigDict(extra="ignore")

    group_id: str = Field(..., min_length=1, max_length=_COORD_PART_MAX_LEN)
    artifact_id: str = Field(..., min_length=1, max_length=_COORD_PART_MAX_LEN)
    version: Optional[str] = None
    scope: Optional[str] = None
    optional: bool = False
    unresolved_reason: Optional[Literal["managed", "property_unresolved", "missing"]] = None

    @field_validator("group_id", "artifact_id")
    @classmethod
    def _strip_and_validate(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("must not be empty")
        return v_stripped


# Tool response models (returned by MCP tools). These are typed and tolerate
# extra upstream fields via model_config.extra = "ignore".


class LatestVersionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    coordinate: MavenCoordinate
    latest: Optional[ArtifactVersionInfo] = None
    # Optional metadata
    stable_filter_applied: Optional[bool] = None
    caveats: list[str] = Field(default_factory=list)


class VersionsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    coordinate: MavenCoordinate
    versions: list[ArtifactVersionInfo]
    # Optional metadata
    stable_filter_applied: Optional[bool] = None
    caveats: list[str] = Field(default_factory=list)


class DeclaredDependenciesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    coordinate: MavenCoordinate
    version: str
    dependencies: list[PomDependency]
    # Optional metadata
    stable_filter_applied: Optional[bool] = None
    caveats: list[str] = Field(default_factory=list)
