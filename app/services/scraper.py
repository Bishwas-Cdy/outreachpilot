import asyncio
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import Settings
from app.services.url_safety import UnsafeURLError, validate_public_url


class ScrapeError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScrapedPage:
    url: str
    title: str
    text: str


class WebsiteScraper:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> ScrapedPage:
        current_url = validate_public_url(url)
        for attempt in range(2):
            try:
                async with client.stream("GET", current_url) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if "text/html" not in content_type.lower():
                        raise ScrapeError("Website did not return HTML")
                    chunks: list[bytes] = []
                    byte_count = 0
                    async for chunk in response.aiter_bytes():
                        byte_count += len(chunk)
                        if byte_count > self.settings.scrape_max_bytes:
                            raise ScrapeError("Website response exceeded the configured size limit")
                        chunks.append(chunk)
                    final_url = str(response.url)
                validate_public_url(final_url)
                soup = BeautifulSoup(b"".join(chunks), "html.parser")
                for element in soup(["script", "style", "noscript", "svg"]):
                    element.decompose()
                text = " ".join(soup.get_text(" ", strip=True).split())
                title = soup.title.get_text(" ", strip=True) if soup.title else ""
                return ScrapedPage(url=final_url, title=title, text=text[:50_000])
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == 1:
                    raise ScrapeError("Website request failed after retry") from exc
                await asyncio.sleep(0.2)
            except (httpx.HTTPStatusError, UnsafeURLError) as exc:
                raise ScrapeError(str(exc)) from exc
        raise ScrapeError("Website request failed")

    async def scrape(self, website: str) -> list[ScrapedPage]:
        validate_public_url(website)
        timeout = httpx.Timeout(self.settings.scrape_timeout_seconds)
        headers = {"User-Agent": "OutreachPilot/0.1 (portfolio research bot)"}
        async with httpx.AsyncClient(
            timeout=timeout, headers=headers, follow_redirects=False
        ) as client:
            home = await self._fetch(client, website)
            candidates: list[str] = []
            # Fetch only a few conventional public pages to keep research bounded.
            for path in ("/about", "/products", "/solutions", "/careers"):
                candidate = urljoin(home.url, path)
                if urlparse(candidate).netloc == urlparse(home.url).netloc:
                    candidates.append(candidate)
            pages = [home]
            results = await asyncio.gather(
                *(self._fetch(client, url) for url in candidates[:3]), return_exceptions=True
            )
            pages.extend(result for result in results if isinstance(result, ScrapedPage))
            return pages
