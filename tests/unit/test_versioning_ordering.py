import pytest

from mcp_maven_central_search.versioning import compare_versions, sort_versions


def test_numeric_ordering_simple():
    assert compare_versions("1.2.10", "1.2.9") == 1
    assert compare_versions("1.10.0", "1.9.9") == 1
    assert compare_versions("2.0", "1.9.9") == 1


def test_mixed_tokens_qualifiers():
    # Final should sort after Beta in a direct compare
    assert compare_versions("1.0.Final", "1.0.Beta1") == 1

    # RELEASE and Final should compare consistently (canonicalized to 'final')
    assert compare_versions("2.0.RELEASE", "2.0.Final") == 0


def test_separators_equivalence():
    # Treat separators '-', '.', '_' equivalently
    assert compare_versions("1.0-1", "1.0.1") == 0
    assert compare_versions("1_2_3", "1.2.3") == 0


def test_weird_inputs_and_prefix_v():
    # Leading 'v' is commonly used
    assert compare_versions("v2", "2") == 0

    # Zero-padding should not affect order
    assert compare_versions("2024.01", "2024.1") == 0

    # Ensure comparator never raises for non-empty odd strings
    assert compare_versions("x", "y") in (-1, 0, 1)


def test_tail_rules_prerelease_vs_missing():
    # Missing tail (stable) should be considered greater than prerelease tail
    assert compare_versions("1.0", "1.0-beta1") == 1
    assert compare_versions("1.0", "1.0-rc1") == 1
    assert compare_versions("1.0", "1.0-m1") == 1


def test_empty_input_raises():
    with pytest.raises(ValueError):
        compare_versions("", "1")
    with pytest.raises(ValueError):
        compare_versions(" \t\n ", "1")
    with pytest.raises(ValueError):
        sort_versions(["1", " "])


def test_determinism_sorting():
    versions = [
        "1.0",
        "1.0-beta1",
        "1.0.Final",
        "1.0.0",
        "1.0-rc1",
        "1.0-m1",
        "1.0.1",
        "v1.0.2",
    ]

    s1 = sort_versions(versions)
    s2 = sort_versions(versions)
    assert s1 == s2
