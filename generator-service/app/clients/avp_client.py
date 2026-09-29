import posixpath
from dataclasses import dataclass
from urllib.parse import unquote, urlparse, urlunparse
from xml.etree import ElementTree

import httpx

SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
AVP_HEADER_SHORTCODE = "{{< avp-header >}}"


@dataclass(frozen=True, slots=True)
class AvpData:
    """Contenu d'un AVP exact récupéré depuis la source officielle."""

    reference: str
    content: str
    source_url: str
    is_archived: bool


class AvpClientError(Exception):
    """Erreur générique d'accès à la source officielle des AVP."""


class AvpNotFoundError(AvpClientError):
    """L'AVP exact demandé est absent du sitemap."""


class AvpInvalidResponseError(AvpClientError):
    """La source officielle des AVP a retourné une réponse inexploitable."""


def normalize_avp_number(avp_number: str) -> str:
    return avp_number.strip().lower().replace("/", "_")


class AvpClient:
    """Récupère un AVP exact dans le sitemap et les fichiers Markdown de l'OPT."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 15.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        parsed_base_url = urlparse(self._base_url)
        self._base_origin = (
            parsed_base_url.scheme.lower(),
            parsed_base_url.hostname,
            parsed_base_url.port,
        )
        self._base_path = posixpath.normpath(unquote(parsed_base_url.path))
        self._http_client = http_client or httpx.AsyncClient(timeout=timeout)

    async def get_avp(self, avp_number: str) -> AvpData:
        """Récupère l'AVP correspondant exactement au numéro fourni."""
        reference = avp_number.strip()
        slug = normalize_avp_number(avp_number)
        sitemap_url = f"{self._base_url}/sitemap.xml"
        sitemap = await self._get_text(sitemap_url, resource="sitemap")
        source_url, is_archived = self._resolve_source(sitemap, slug)
        markdown_url = self._markdown_url(source_url)
        markdown = await self._get_text(markdown_url, resource="markdown")
        content = markdown.replace(AVP_HEADER_SHORTCODE, "").strip()
        if not content:
            raise AvpInvalidResponseError("Le contenu Markdown de l'AVP est vide")
        return AvpData(
            reference=reference,
            content=content,
            source_url=markdown_url,
            is_archived=is_archived,
        )

    async def aclose(self) -> None:
        await self._http_client.aclose()

    async def _get_text(self, url: str, *, resource: str) -> str:
        try:
            response = await self._http_client.get(url)
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise AvpClientError(
                f"La requête AVP vers {resource} a dépassé le délai autorisé"
            ) from error
        except httpx.HTTPError as error:
            raise AvpClientError(f"La requête AVP vers {resource} a échoué") from error
        content_type = response.headers.get("content-type", "").lower()
        if content_type and not (
            content_type.startswith("text/")
            or content_type.startswith("application/xml")
        ):
            raise AvpInvalidResponseError(
                f"La ressource AVP {resource} n'est pas textuelle"
            )
        return response.text

    def _resolve_source(self, sitemap: str, slug: str) -> tuple[str, bool]:
        try:
            root = ElementTree.fromstring(sitemap)
        except ElementTree.ParseError as error:
            raise AvpInvalidResponseError(
                "Le XML du sitemap AVP est invalide"
            ) from error

        expected_root = f"{{{SITEMAP_NAMESPACE}}}urlset"
        if root.tag != expected_root:
            raise AvpInvalidResponseError("La structure du sitemap AVP est invalide")
        locations = root.findall(f".//{{{SITEMAP_NAMESPACE}}}loc")
        if not locations:
            raise AvpInvalidResponseError("Le sitemap AVP ne contient aucune URL")

        active: set[str] = set()
        archived: set[str] = set()
        for location in locations:
            if location.text is None:
                continue
            url = location.text.strip()
            parsed = urlparse(url)
            if not self._is_allowed_source(parsed):
                continue
            segments = [
                segment.lower()
                for segment in unquote(parsed.path).split("/")
                if segment
            ]
            if (
                len(segments) < 2
                or segments[-1] != "index.html"
                or segments[-2] != slug
            ):
                continue
            target = archived if "archives" in segments else active
            target.add(url)

        candidates = active or archived
        if not candidates:
            raise AvpNotFoundError("AVP introuvable")
        if len(candidates) != 1:
            raise AvpInvalidResponseError("Le résultat du sitemap AVP est ambigu")
        return next(iter(candidates)), not bool(active)

    def _is_allowed_source(self, parsed_url: object) -> bool:
        if not hasattr(parsed_url, "scheme"):
            return False
        origin = (
            parsed_url.scheme.lower(),
            parsed_url.hostname,
            parsed_url.port,
        )
        if origin != self._base_origin:
            return False
        candidate_path = posixpath.normpath(unquote(parsed_url.path))
        if self._base_path == "/":
            return candidate_path.startswith("/")
        return candidate_path.startswith(f"{self._base_path}/")

    @staticmethod
    def _markdown_url(source_url: str) -> str:
        parsed = urlparse(source_url)
        if not parsed.path.endswith("/index.html"):
            raise AvpInvalidResponseError("L'URL source de l'AVP est invalide")
        path = f"{parsed.path.removesuffix('index.html')}index.md"
        return urlunparse(parsed._replace(path=path, query="", fragment=""))
