"""Version stability detection and ordering utilities.

Specification reference:

- PLANNING.md → "Version Filtering & Ordering (versioning.py)"
- Issue #10 — PLAN-2.1
- Issue #11 — PLAN-2.2

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
from functools import cmp_to_key
from typing import Final, Iterable, List, Sequence, Union

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


# -----------------------------
# PLAN-2.2 — Version ordering
# -----------------------------

_SEP_PATTERN: Final[re.Pattern[str]] = re.compile(r"[._-]+")
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"\d+|[A-Za-z]+")

# Canonical maps for common qualifiers to keep comparisons sensible
_CANON_MAP: Final[dict[str, str]] = {
    # Stable synonyms
    "release": "final",
    "ga": "final",
    # RC alias
    "cr": "rc",
}

_STABLE_SYNONYMS: Final[frozenset[str]] = frozenset({"final", "release", "ga"})
_PRERELEASE_QUALS: Final[frozenset[str]] = frozenset(
    {"snapshot", "alpha", "beta", "rc", "cr", "milestone", "m", "preview", "ea"}
)


def _normalize_version_prefix(s: str) -> str:
    # Drop a leading 'v' prefix commonly used, e.g. v2.0
    if s and (s[0] == "v" or s[0] == "V"):
        if len(s) > 1 and s[1].isdigit():
            return s[1:]
    return s


def _tokenize(version: str) -> List[Union[int, str]]:
    """Split a version into numeric and alpha tokens.

    Separators '.', '-', '_' are treated equivalently. Non [A-Za-z0-9] chars are
    effectively treated as separators by design. Numeric tokens become ints,
    alpha tokens are lower-cased and canonicalized via _CANON_MAP.
    """
    s = _normalize_version_prefix(_validate_input(version))
    # Normalize separators to '.' then split into coarse parts
    parts = [p for p in _SEP_PATTERN.split(s) if p != ""]
    tokens: List[Union[int, str]] = []
    for part in parts:
        for tok in _TOKEN_PATTERN.findall(part):
            if tok.isdigit():
                # Convert to int (Python ints are unbounded)
                tokens.append(int(tok))
            else:
                low = tok.lower()
                # Use explicit membership to avoid Optional[str] from dict.get for type checker
                low = _CANON_MAP[low] if low in _CANON_MAP else low
                tokens.append(low)
    return tokens


def _tail_significance(tokens: Sequence[Union[int, str]], start: int) -> str:
    """Classify the significance of the remaining tokens starting at index.

    Returns one of: 'none', 'prerelease', 'meaningful'.
    - 'none' => only zeros or stable markers remain -> treat as equal
    - 'prerelease' => first meaningful token is a prerelease qualifier -> shorter wins
    - 'meaningful' => there is numeric>0 or other qualifier -> longer wins
    """
    significance = "none"
    i = start
    while i < len(tokens):
        t = tokens[i]
        if isinstance(t, int):
            if t == 0:
                i += 1
                continue
            return "meaningful"
        # str token
        tl = t.lower()
        tl = _CANON_MAP.get(tl, tl)
        if tl in _STABLE_SYNONYMS:
            i += 1
            continue
        if tl in _PRERELEASE_QUALS:
            # Consider prerelease tails as less than missing
            return "prerelease"
        # Other non-empty qualifier -> meaningful
        return "meaningful"
    return significance


def compare_versions(a: str, b: str) -> int:
    """Compare two version strings.

    Returns -1 if a < b, 0 if equal, 1 if a > b. Never raises for odd inputs
    except when an input is empty/whitespace (raises ValueError).

    Heuristics per PLAN-2.2:
    - Tokenize into alternating numeric and non-numeric tokens, treating
      '.', '-', '_' as equivalent separators
    - Compare numeric tokens as integers; non-numeric case-insensitive with
      simple canonicalization
    - If tokens equal but one has a remaining tail:
        * ignore zeros and stable markers (RELEASE/Final/GA)
        * if tail indicates prerelease (alpha/beta/rc/m/ea/preview/snapshot)
          then the shorter (stable) sorts after
        * otherwise, prefer the longer
    """
    ta = _tokenize(a)
    tb = _tokenize(b)

    # Compare token-by-token
    i = 0
    while i < len(ta) and i < len(tb):
        xa = ta[i]
        xb = tb[i]

        if isinstance(xa, int) and isinstance(xb, int):
            if xa < xb:
                return -1
            if xa > xb:
                return 1
        elif isinstance(xa, str) and isinstance(xb, str):
            sa = _CANON_MAP.get(xa, xa)
            sb = _CANON_MAP.get(xb, xb)
            # Non-numeric compare case-insensitive
            if sa < sb:
                return -1
            if sa > sb:
                return 1
        else:
            # Prefer numeric over non-numeric (e.g., 1.0.1 > 1.0.final)
            if isinstance(xa, int):
                return 1
            else:
                return -1
        i += 1

    # Tokens equal up to min length; consider tails
    if len(ta) == len(tb):
        return 0

    if i < len(ta):
        tail_a = _tail_significance(ta, i)
        if tail_a == "none":
            # consider equal when tail is only zeros/stable markers
            return 0
        if tail_a == "prerelease":
            # a has prerelease tail; missing tail in b means b is greater
            return -1
        return 1

    # a ran out first
    tail_b = _tail_significance(tb, i)
    if tail_b == "none":
        return 0
    if tail_b == "prerelease":
        return 1
    return -1


def sort_versions(versions: Iterable[str]) -> list[str]:
    """Return a new list of versions sorted using :func:`compare_versions`.

    The result is deterministic. Invalid (empty/whitespace) entries will raise
    ValueError.
    """
    # Materialize first to validate inputs deterministically
    items = list(versions)
    for v in items:
        _ = _validate_input(v)
    return sorted(items, key=cmp_to_key(compare_versions))
