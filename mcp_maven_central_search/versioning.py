"""Version stability detection utilities.

Specification reference:

- PLANNING.md → "Version Filtering & Ordering (versioning.py)"
- Issue #10 — PLAN-2.1

Rules (v1):

- Treat as pre-release if version contains any of the following qualifiers
  (case-insensitive; tolerant of separators like '-', '.', '_'):
    - SNAPSHOT
    - alpha, beta, rc, cr, milestone, preview, ea
    - the token "m" only when used as a milestone shorthand with a numeric
      suffix, e.g. "-m1", ".m2", "_M3"
- Stable markers RELEASE, Final, GA are allowed and considered stable, but do
  not override explicit pre-release qualifiers if present.
"""

from __future__ import annotations

import re
from typing import Final

# Simple substring for SNAPSHOT (anywhere, any case)
_SNAPSHOT: Final[re.Pattern[str]] = re.compile(r"snapshot", re.IGNORECASE)

# Qualifiers that indicate pre-release when they appear as a token separated by
# common separators or string boundaries. Digits may follow (e.g. rc1, beta2).
_PRERELEASE_QUALIFIERS: Final[re.Pattern[str]] = re.compile(
    r"(?ix)"  # ignore-case, verbose
    r"(?:^|[._-])"  # start or common separator
    r"(alpha|beta|rc|cr|milestone|preview|ea)"  # qualifier
    r"\d*"  # optional digits
    r"(?=$|[._-])"  # end or separator
)

# Milestone shorthand: the single letter 'm' only when followed by digits and
# delimited by separators or string boundaries, e.g. -m1, .m2, _M3.
_MILESTONE_M: Final[re.Pattern[str]] = re.compile(
    r"(?ix)"  # ignore-case, verbose
    r"(?:^|[._-])"  # start or separator
    r"m"  # literal m
    r"\d+"  # one or more digits required
    r"(?=$|[._-])"  # end or separator
)

# Stable markers — these suggest a release build when present as tokens.
_STABLE_MARKERS: Final[re.Pattern[str]] = re.compile(
    r"(?ix)(?:^|[._-])(release|final|ga)(?=$|[._-])"
)


def _validate_input(version: str) -> str:
    if version is None:
        raise ValueError("version must be a non-empty string, got None")
    s = version.strip()
    if not s:
        raise ValueError("version must be a non-empty string")
    return s


def is_prerelease(version: str) -> bool:
    """Return True if the given version string represents a pre-release.

    The detection follows PLAN-2.1 stable filtering rules and is intentionally
    conservative: only well-known pre-release markers and milestone patterns
    trigger a pre-release classification. The function is deterministic and
    will not raise on unusual strings (aside from empty input validation).
    """

    s = _validate_input(version)

    # Fast path: any occurrence of SNAPSHOT anywhere
    if _SNAPSHOT.search(s):
        return True

    # Qualifier-based detection (alpha/beta/rc/cr/milestone/preview/ea)
    if _PRERELEASE_QUALIFIERS.search(s):
        return True

    # Milestone shorthand: -m1 / .m2 / _m3 … but not letters like "something"
    if _MILESTONE_M.search(s):
        return True

    return False


def is_stable(version: str) -> bool:
    """Return True if the given version string should be treated as stable.

    Stable is defined as NOT pre-release per :func:`is_prerelease`.
    Stable markers like RELEASE/Final/GA are allowed but do not override an
    explicit pre-release marker if one is present.
    """

    s = _validate_input(version)
    if is_prerelease(s):
        return False

    # Presence of stable markers reinforces stability but is not required.
    # We simply accept as stable if no pre-release markers were found.
    return True
