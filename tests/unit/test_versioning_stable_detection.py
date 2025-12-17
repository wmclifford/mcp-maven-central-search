import pytest

from mcp_maven_central_search.versioning import is_prerelease, is_stable


class TestStableDetection:
    # Stable examples
    @pytest.mark.parametrize(
        "v",
        [
            "1.2.3",
            "1.0",
            "1.0.Final",
            "2.0.RELEASE",
            "3.1.0-GA",
        ],
    )
    def test_stable_examples(self, v: str) -> None:
        assert is_stable(v) is True
        assert is_prerelease(v) is False

    # Pre-release examples
    @pytest.mark.parametrize(
        "v",
        [
            "1.0-SNAPSHOT",
            "2.0-rc1",
            "2.0.RC2",
            "1.0-beta",
            "1.0.BETA1",
            "1.0-alpha",
            "1.0.ALPHA2",
            "1.0-m1",
            "1.0.M2",
            "1.0-preview",
            "1.0-ea",
        ],
    )
    def test_prerelease_examples(self, v: str) -> None:
        assert is_prerelease(v) is True
        assert is_stable(v) is False

    # Edge cases
    def test_m_not_inside_words(self) -> None:
        # Should not treat the 'm' in 'something' as a milestone shorthand
        v = "1.0-something"
        assert is_prerelease(v) is False
        assert is_stable(v) is True

    @pytest.mark.parametrize("bad", ["", "   "])
    def test_empty_or_whitespace_raises(self, bad: str) -> None:
        with pytest.raises(ValueError):
            is_stable(bad)
        with pytest.raises(ValueError):
            is_prerelease(bad)
