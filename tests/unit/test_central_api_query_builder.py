import pytest

from mcp_maven_central_search.central_api import (
    build_ga_query,
    build_params_for_search,
    build_params_for_versions,
)


def test_build_ga_query_basic():
    q = build_ga_query("org.apache.commons", "commons-lang3")
    assert q == 'g:"org.apache.commons" AND a:"commons-lang3"'


def test_build_ga_query_escaping_quotes_and_backslashes():
    q = build_ga_query('com.example"weird', r"art\ifact")
    # Expect embedded quote and backslash to be escaped inside the quoted literal
    assert q == 'g:"com.example\\"weird" AND a:"art\\\\ifact"'


def test_build_params_for_versions_contains_required_keys():
    params = build_params_for_versions("g", "a", 25)
    assert params["core"] == "gav"
    assert params["wt"] == "json"
    assert params["rows"] == 25
    assert params["q"] == 'g:"g" AND a:"a"'


def test_build_params_for_search_contains_required_keys():
    params = build_params_for_search("kotlin coroutine", 10)
    assert params == {"q": "kotlin coroutine", "rows": 10, "wt": "json"}


@pytest.mark.parametrize(
    "group_id, artifact_id",
    [
        ("", "a"),
        (" ", "a"),
        ("g", ""),
        ("g", " "),
    ],
)
def test_build_ga_query_validation_empty(group_id, artifact_id):
    with pytest.raises(ValueError):
        build_ga_query(group_id, artifact_id)


def test_build_ga_query_validation_too_long():
    long = "x" * 201
    with pytest.raises(ValueError):
        build_ga_query(long, "a")
    with pytest.raises(ValueError):
        build_ga_query("g", long)


@pytest.mark.parametrize("rows", [0, -1, 1.5])
def test_rows_validation_versions(rows):
    with pytest.raises(ValueError):
        build_params_for_versions("g", "a", rows)  # type: ignore[arg-type]


@pytest.mark.parametrize("rows", [0, -5])
def test_rows_validation_search(rows):
    with pytest.raises(ValueError):
        build_params_for_search("ok", rows)


def test_search_validation_query_empty_and_too_long():
    with pytest.raises(ValueError):
        build_params_for_search(" \t\n", 5)
    long_q = "x" * 1001
    with pytest.raises(ValueError):
        build_params_for_search(long_q, 5)
