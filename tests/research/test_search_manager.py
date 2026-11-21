from app.research.providers import SearchProviderError
from app.research.search_manager import SearchManager
from app.research.search_models import SearchResult


class FakeProvider:
    def __init__(self, name, results=None, available=True):
        self.name = name
        self.results = results or []
        self.available = available

    def health_check(self):
        return self.available

    def search(self, query, *, limit=5):
        if not self.available:
            raise SearchProviderError(f"{self.name} unavailable")
        return self.results[:limit]


def test_search_manager_auto_falls_back_to_searxng():
    brave = FakeProvider("brave", available=False)
    searxng = FakeProvider(
        "searxng",
        [SearchResult(
            title="Laravel",
            url="https://laravel.com/docs",
            snippet="Official docs",
            domain="laravel.com",
            provider="searxng",
        )],
    )
    manager = SearchManager(brave, searxng, mode="auto")

    results = manager.search("current Laravel")

    assert results[0]["provider"] == "searxng"
    assert results[0]["url"] == "https://laravel.com/docs"


def test_search_manager_deduplicates_urls():
    provider_a = FakeProvider(
        "brave",
        [SearchResult("A", "https://example.com/docs", "A", "example.com", "brave")],
    )
    provider_b = FakeProvider(
        "searxng",
        [SearchResult("A", "https://example.com/docs/", "B", "example.com", "searxng")],
    )
    manager = SearchManager(provider_a, provider_b, mode="compare")

    results = manager.search("example")

    assert len(results) == 1


def test_search_manager_reports_all_providers_unavailable():
    manager = SearchManager(
        FakeProvider("brave", available=False),
        FakeProvider("searxng", available=False),
        mode="auto",
    )

    try:
        manager.search("current information")
        assert False
    except SearchProviderError as exc:
        assert "unavailable" in str(exc).lower()
