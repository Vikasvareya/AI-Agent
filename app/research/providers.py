import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.research.search_models import SearchResult


class SearchProviderError(RuntimeError):
    pass


class BraveSearchProvider:
    def __init__(self, api_key: str | None, *, timeout: float = 10):
        self.api_key = api_key.strip() if isinstance(api_key, str) else ""
        self.timeout = timeout
        self.name = "brave"

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def health_check(self) -> bool:
        return self.available

    def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        if not self.available:
            raise SearchProviderError("Brave Search is not configured.")
        request = Request(
            f"https://api.search.brave.com/res/v1/web/search?"
            f"{urlencode({'q': query, 'count': limit})}",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
                "User-Agent": "AI-Brain/1.0",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read(1_000_000))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise SearchProviderError("Brave Search is unavailable.") from exc
        web_results = payload.get("web", {}) if isinstance(payload, dict) else {}
        rows = web_results.get("results", []) if isinstance(web_results, dict) else []
        results = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url", "")).strip()
            if not url:
                continue
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.lower()
            except Exception:
                domain = ""
            results.append(SearchResult(
                title=str(row.get("title", "Untitled"))[:300],
                url=url[:2000],
                snippet=str(row.get("description", ""))[:2000],
                domain=domain,
                provider="brave",
                published_at=row.get("page_age") if isinstance(row.get("page_age"), str) else None,
                metadata={"source": "brave"},
            ))
        return results


class SearXNGProvider:
    def __init__(
        self,
        base_url: str | None,
        *,
        enabled: bool = False,
        timeout: float = 15,
        categories: str = "general",
    ):
        self.base_url = base_url.rstrip("/") if isinstance(base_url, str) else ""
        self.enabled = enabled
        self.timeout = timeout
        self.categories = categories or "general"
        self.name = "searxng"

    @property
    def available(self) -> bool:
        return self.enabled and bool(self.base_url)

    def health_check(self) -> bool:
        if not self.available:
            return False
        try:
            request = Request(
                f"{self.base_url}/healthz",
                headers={"Accept": "application/json"},
            )
            with urlopen(request, timeout=min(self.timeout, 5)) as response:
                return 200 <= response.status < 300
        except (HTTPError, URLError, TimeoutError, OSError):
            return False

    def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        if not self.available:
            raise SearchProviderError("SearXNG is not configured.")
        params = urlencode({
            "q": query,
            "format": "json",
            "categories": self.categories,
        })
        request = Request(
            f"{self.base_url}/search?{params}",
            headers={
                "Accept": "application/json",
                "User-Agent": "AI-Brain/1.0",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read(2_000_000))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise SearchProviderError("SearXNG is unavailable.") from exc
        rows = payload.get("results", []) if isinstance(payload, dict) else []
        results = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url", "")).strip()
            if not url:
                continue
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.lower()
            except Exception:
                domain = ""
            results.append(SearchResult(
                title=str(row.get("title", "Untitled"))[:300],
                url=url[:2000],
                snippet=str(row.get("content", ""))[:2000],
                domain=domain,
                provider="searxng",
                published_at=row.get("publishedDate") if isinstance(row.get("publishedDate"), str) else None,
                metadata={"source": "searxng", "engines": row.get("engines", [])},
            ))
        return results
