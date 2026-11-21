from dataclasses import dataclass, field


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    domain: str
    provider: str
    published_at: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "description": self.snippet,
            "domain": self.domain,
            "provider": self.provider,
            "published_at": self.published_at,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class PageResult:
    canonical_url: str
    title: str
    domain: str
    content: str
    published_at: str | None = None
