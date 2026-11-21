import ipaddress
import socket
from urllib.parse import urljoin, urlparse

from app.research.providers import SearchProviderError
from app.research.search_models import SearchResult


class SearchManager:
    def __init__(
        self,
        brave,
        searxng,
        *,
        mode: str = "auto",
        fallback_enabled: bool = True,
    ):
        if mode not in ("auto", "brave", "searxng", "compare"):
            raise ValueError("Search provider mode must be auto, brave, searxng, or compare.")
        self.brave = brave
        self.searxng = searxng
        self.mode = mode
        self.fallback_enabled = fallback_enabled

    @property
    def available(self) -> bool:
        return bool(
            (self.brave.available and self.brave.health_check())
            or (self.searxng.available and self.searxng.health_check())
        )

    def provider_status(self) -> dict:
        return {
            "active_mode": self.mode,
            "brave": {
                "configured": bool(self.brave.available),
                "healthy": bool(self.brave.available and self.brave.health_check()),
            },
            "searxng": {
                "configured": bool(self.searxng.available),
                "healthy": bool(self.searxng.available and self.searxng.health_check()),
            },
        }

    def search(self, query: str, *, limit: int = 5) -> list[dict]:
        if not isinstance(query, str) or not query.strip() or len(query) > 400:
            raise SearchProviderError("Search queries must be 1-400 characters.")
        limit = max(1, min(limit, 10))
        providers = self._providers_for_mode()
        last_error = None
        combined = []
        for provider in providers:
            try:
                if not provider.available:
                    continue
                combined.extend(provider.search(query.strip(), limit=limit))
                if self.mode != "compare":
                    break
            except SearchProviderError as exc:
                last_error = exc
                if not self.fallback_enabled:
                    break
        if not combined:
            if last_error:
                raise last_error
            raise SearchProviderError(
                "Web research is unavailable. Configure Brave Search or connect SearXNG."
            )
        return [result.to_dict() for result in self.normalize(combined)[:limit]]

    def _providers_for_mode(self):
        if self.mode == "brave":
            return [self.brave]
        if self.mode == "searxng":
            return [self.searxng]
        if self.mode == "compare":
            return [self.brave, self.searxng]
        return [self.brave, self.searxng]

    @staticmethod
    def normalize(results: list[SearchResult]) -> list[SearchResult]:
        deduplicated = {}
        for result in results:
            normalized_url = result.url.strip()
            try:
                parsed = urlparse(normalized_url)
                path = (parsed.path or "/").rstrip("/")
                if not path:
                    path = "/"
                normalized_url = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"
            except Exception:
                continue
            if normalized_url not in deduplicated:
                deduplicated[normalized_url] = SearchResult(
                    title=result.title.strip()[:300],
                    url=result.url,
                    snippet=result.snippet.strip()[:2000],
                    domain=result.domain.lower(),
                    provider=result.provider,
                    published_at=result.published_at,
                    metadata=result.metadata,
                )
        return list(deduplicated.values())
