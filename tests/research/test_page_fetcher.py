from app.research.page_fetcher import PageFetcher, UnsafeUrlError


def test_page_fetcher_blocks_loopback_urls():
    fetcher = PageFetcher()

    try:
        fetcher.fetch("http://127.0.0.1/admin")
        assert False
    except UnsafeUrlError:
        pass


def test_page_fetcher_blocks_private_urls():
    fetcher = PageFetcher()

    try:
        fetcher.fetch("http://10.0.0.1/private")
        assert False
    except UnsafeUrlError:
        pass
