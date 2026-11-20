import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)

_SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_ -]?key|secret|password|credential|access[_ -]?token)"
    r"\s*(?:is|:|=)\s*\S+|"
    r"\bAKIA[0-9A-Z]{16}\b|"
    r"\bsk-[A-Za-z0-9_-]{20,}\b|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b|"
    r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b|"
    r"\bBearer\s+[A-Za-z0-9._~+/-]{12,}|"
    r"\b[A-Za-z0-9+/_=-]{40,}\b|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
)
_CODE_PATTERN = re.compile(
    r"```|^\s*(?:def\s+\w+\s*\(|class\s+\w+|function\s+\w+\s*\(|"
    r"import\s+\w+|#include\s*[<\"]|SELECT\s+.+\s+FROM\s+)|"
    r"[{};]|=>",
    re.MULTILINE | re.IGNORECASE,
)


class WebSearchError(Exception):
    pass


class BraveWebSearch:
    _ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str | None, *, timeout: float = 10):
        self.api_key = api_key.strip() if isinstance(api_key, str) else ""
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        if not self.available:
            raise WebSearchError("Web search is not configured.")
        if not isinstance(query, str) or not query.strip() or len(query) > 400:
            raise WebSearchError("Web search queries must be 1-400 characters.")
        if _SECRET_PATTERN.search(query) or _CODE_PATTERN.search(query):
            raise WebSearchError(
                "Remove credentials and source code from web search queries."
            )
        request = Request(
            f"{self._ENDPOINT}?{urlencode({'q': query.strip(), 'count': limit})}",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
                "User-Agent": "AI-Agent-Framework/1.0",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read(1_000_000))
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            logger.warning("Brave web search failed: %s", exc)
            raise WebSearchError("The web search provider is temporarily unavailable.") from exc

        web_results = payload.get("web") if isinstance(payload, dict) else None
        results = web_results.get("results") if isinstance(web_results, dict) else None
        if not isinstance(results, list):
            raise WebSearchError("The web search provider returned an invalid response.")
        sources = []
        for result in results[:limit]:
            url = result.get("url")
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                continue
            sources.append(
                {
                    "title": str(result.get("title", "Untitled result"))[:300],
                    "url": url[:2000],
                    "description": str(result.get("description", ""))[:2000],
                }
            )
        return sources
