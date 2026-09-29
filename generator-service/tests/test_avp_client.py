import httpx
import pytest
from app.clients.avp_client import (
    AVP_HEADER_SHORTCODE,
    AvpClient,
    AvpClientError,
    AvpInvalidResponseError,
    AvpNotFoundError,
    normalize_avp_number,
)

BASE_URL = "https://opt.example/odata-avps"
REFERENCE = "3134-26-1382/SR"
SLUG = "3134-26-1382_sr"


def sitemap(*locations: str) -> str:
    urls = "".join(f"<url><loc>{location}</loc></url>" for location in locations)
    return (
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    )


def make_client(handler: httpx.MockTransport) -> AvpClient:
    return AvpClient(
        base_url=BASE_URL,
        http_client=httpx.AsyncClient(transport=handler),
    )


def test_normalize_avp_number() -> None:
    assert normalize_avp_number("  3134-26-1382/SR  ") == SLUG


@pytest.mark.asyncio
async def test_get_active_avp_resolves_exact_url_and_cleans_markdown() -> None:
    html_url = f"{BASE_URL}/dps/{SLUG}/index.html"
    markdown_url = f"{BASE_URL}/dps/{SLUG}/index.md"
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.path.endswith("sitemap.xml"):
            return httpx.Response(200, text=sitemap(html_url))
        assert str(request.url) == markdown_url
        return httpx.Response(200, text=f"{AVP_HEADER_SHORTCODE}\n# Missions\n- Test")

    client = make_client(httpx.MockTransport(handler))
    avp = await client.get_avp(f"  {REFERENCE}  ")

    assert requested_urls == [f"{BASE_URL}/sitemap.xml", markdown_url]
    assert avp.reference == REFERENCE
    assert avp.source_url == markdown_url
    assert avp.content == "# Missions\n- Test"
    assert AVP_HEADER_SHORTCODE not in avp.content
    assert avp.is_archived is False
    await client.aclose()


@pytest.mark.asyncio
async def test_get_avp_falls_back_to_archive() -> None:
    html_url = f"{BASE_URL}/archives/{SLUG}/index.html"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("sitemap.xml"):
            return httpx.Response(200, text=sitemap(html_url))
        assert request.url.path.endswith(f"/archives/{SLUG}/index.md")
        return httpx.Response(200, text="# Poste archivé")

    client = make_client(httpx.MockTransport(handler))
    avp = await client.get_avp(REFERENCE)
    assert avp.is_archived is True
    await client.aclose()


@pytest.mark.asyncio
async def test_active_avp_is_preferred_over_archive() -> None:
    active = f"{BASE_URL}/dsi/{SLUG}/index.html"
    archive = f"{BASE_URL}/archives/{SLUG}/index.html"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("sitemap.xml"):
            return httpx.Response(200, text=sitemap(archive, active))
        assert request.url.path.endswith(f"/dsi/{SLUG}/index.md")
        return httpx.Response(200, text="# Poste actif")

    client = make_client(httpx.MockTransport(handler))
    avp = await client.get_avp(REFERENCE)
    assert avp.content == "# Poste actif"
    assert avp.is_archived is False
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "requested",
    ["0000-00-0000/SR", "3134-26-138"],
)
async def test_absent_or_partial_avp_does_not_match(requested: str) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            text=sitemap(f"{BASE_URL}/dps/{SLUG}/index.html"),
        )
    )
    client = make_client(transport)
    with pytest.raises(AvpNotFoundError):
        await client.get_avp(requested)
    await client.aclose()


@pytest.mark.asyncio
async def test_invalid_sitemap_xml_is_rejected() -> None:
    client = make_client(
        httpx.MockTransport(lambda request: httpx.Response(200, text="<urlset>"))
    )
    with pytest.raises(AvpInvalidResponseError):
        await client.get_avp(REFERENCE)
    await client.aclose()


@pytest.mark.asyncio
async def test_invalid_sitemap_structure_is_rejected() -> None:
    client = make_client(
        httpx.MockTransport(lambda request: httpx.Response(200, text="<urlset />"))
    )
    with pytest.raises(AvpInvalidResponseError):
        await client.get_avp(REFERENCE)
    await client.aclose()


@pytest.mark.asyncio
async def test_sitemap_http_error_is_controlled() -> None:
    client = make_client(
        httpx.MockTransport(lambda request: httpx.Response(500, text="private"))
    )
    with pytest.raises(AvpClientError, match="requête AVP vers sitemap a échoué"):
        await client.get_avp(REFERENCE)
    await client.aclose()


@pytest.mark.asyncio
async def test_sitemap_timeout_is_controlled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    client = make_client(httpx.MockTransport(handler))
    with pytest.raises(AvpClientError, match="dépassé le délai autorisé"):
        await client.get_avp(REFERENCE)
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("markdown_status,markdown_text", [(500, "error"), (200, "  ")])
async def test_invalid_markdown_is_rejected(
    markdown_status: int,
    markdown_text: str,
) -> None:
    html_url = f"{BASE_URL}/dt/{SLUG}/index.html"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("sitemap.xml"):
            return httpx.Response(200, text=sitemap(html_url))
        return httpx.Response(markdown_status, text=markdown_text)

    client = make_client(httpx.MockTransport(handler))
    expected = AvpClientError if markdown_status == 500 else AvpInvalidResponseError
    with pytest.raises(expected):
        await client.get_avp(REFERENCE)
    await client.aclose()


@pytest.mark.asyncio
async def test_multiple_exact_active_matches_are_rejected() -> None:
    locations = (
        f"{BASE_URL}/dps/{SLUG}/index.html",
        f"{BASE_URL}/dsi/{SLUG}/index.html",
    )
    client = make_client(
        httpx.MockTransport(
            lambda request: httpx.Response(200, text=sitemap(*locations))
        )
    )
    with pytest.raises(AvpInvalidResponseError, match="ambigu"):
        await client.get_avp(REFERENCE)
    await client.aclose()


@pytest.mark.asyncio
async def test_multiple_exact_archive_matches_are_rejected() -> None:
    locations = (
        f"{BASE_URL}/archives/{SLUG}/index.html",
        f"{BASE_URL}/legacy/archives/{SLUG}/index.html",
    )
    client = make_client(
        httpx.MockTransport(
            lambda request: httpx.Response(200, text=sitemap(*locations))
        )
    )
    with pytest.raises(AvpInvalidResponseError, match="ambigu"):
        await client.get_avp(REFERENCE)
    await client.aclose()


@pytest.mark.asyncio
async def test_exact_avp_outside_configured_origin_is_never_fetched() -> None:
    external_url = f"https://cdn.example/archives/{SLUG}/index.html"
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text=sitemap(external_url))

    client = make_client(httpx.MockTransport(handler))
    with pytest.raises(AvpNotFoundError):
        await client.get_avp(REFERENCE)
    assert requested_urls == [f"{BASE_URL}/sitemap.xml"]
    await client.aclose()


@pytest.mark.asyncio
async def test_exact_avp_outside_configured_base_path_is_never_fetched() -> None:
    external_path = f"https://opt.example/other/{SLUG}/index.html"
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text=sitemap(external_path))

    client = make_client(httpx.MockTransport(handler))
    with pytest.raises(AvpNotFoundError):
        await client.get_avp(REFERENCE)
    assert requested_urls == [f"{BASE_URL}/sitemap.xml"]
    await client.aclose()
