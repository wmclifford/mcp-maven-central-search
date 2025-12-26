import pytest

from mcp_maven_central_search.config import Settings


def test_defaults_representative_fields():
    s = Settings()
    assert s.MAVEN_CENTRAL_BASE_URL == "https://central.sonatype.com/solrsearch/select"
    assert s.HTTP_TIMEOUT_SECONDS == 10
    assert s.CACHE_ENABLED is True
    assert s.LOG_LEVEL == "INFO"
    assert s.TRANSPORT == "stdio"


def test_env_overrides_str_int_bool(monkeypatch: pytest.MonkeyPatch):
    # Override a string
    monkeypatch.setenv("MAVEN_CENTRAL_BASE_URL", "https://example.invalid/search")
    # Override an int
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", "25")
    # Override a bool
    monkeypatch.setenv("CACHE_ENABLED", "false")

    s = Settings()  # picks up env vars

    assert s.MAVEN_CENTRAL_BASE_URL == "https://example.invalid/search"
    assert s.HTTP_TIMEOUT_SECONDS == 25
    assert s.CACHE_ENABLED is False


def test_env_isolation(monkeypatch: pytest.MonkeyPatch):
    # Ensure no leakage between tests by clearing relevant vars
    for key in [
        "MAVEN_CENTRAL_BASE_URL",
        "HTTP_TIMEOUT_SECONDS",
        "CACHE_ENABLED",
    ]:
        monkeypatch.delenv(key, raising=False)

    s = Settings()
    assert s.MAVEN_CENTRAL_BASE_URL == "https://central.sonatype.com/solrsearch/select"
    assert s.HTTP_TIMEOUT_SECONDS == 10
    assert s.CACHE_ENABLED is True
