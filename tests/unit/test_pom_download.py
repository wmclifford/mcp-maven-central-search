import httpx
import pytest
import respx

from mcp_maven_central_search.pom import download_pom


@pytest.mark.asyncio
async def test_constructs_canonical_url_and_downloads() -> None:
    group = "org.example"
    artifact = "demo"
    version = "1.2.3"
    expected_url = "https://repo1.maven.org/maven2/org/example/demo/1.2.3/demo-1.2.3.pom"

    xml = """<project><modelVersion>4.0.0</modelVersion></project>"""

    with respx.mock(assert_all_called=True) as router:
        route = router.get(expected_url).mock(
            return_value=httpx.Response(200, content=xml.encode("utf-8"))
        )
        text = await download_pom(group, artifact, version)
        assert xml == text
        assert route.called


@pytest.mark.asyncio
async def test_404_propagates_http_error() -> None:
    url = "https://repo1.maven.org/maven2/com/acme/lib/0.0.1/lib-0.0.1.pom"
    with respx.mock(assert_all_called=True) as router:
        router.get(url).mock(return_value=httpx.Response(404, text="not found"))
        with pytest.raises(httpx.HTTPStatusError):
            await download_pom("com.acme", "lib", "0.0.1")


@pytest.mark.asyncio
async def test_oversized_response_is_rejected() -> None:
    # single chunk larger than cap should be rejected
    big = b"x" * (2_000_000 + 1)
    url = "https://repo1.maven.org/maven2/com/acme/big/9.9.9/big-9.9.9.pom"
    with respx.mock(assert_all_called=True) as router:
        router.get(url).mock(return_value=httpx.Response(200, content=big))
        with pytest.raises(ValueError):
            await download_pom("com.acme", "big", "9.9.9")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "group,artifact,version",
    [
        ("", "a", "1"),
        ("com.acme", "", "1"),
        ("com.acme", "a", ""),
        ("/bad", "a", "1"),
        ("com..acme", "a", "1"),
        ("com.acme", "a/../../b", "1"),
        ("com.acme", "a", "../1"),
    ],
)
async def test_invalid_inputs_raise_value_error(group: str, artifact: str, version: str) -> None:
    with pytest.raises(ValueError):
        await download_pom(group, artifact, version)
