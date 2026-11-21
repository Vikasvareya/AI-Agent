import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


class UnsafeUrlError(ValueError):
    pass


class PageFetchError(RuntimeError):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.title_parts = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text:
            return
        if self.in_title:
            self.title_parts.append(text)
        else:
            self.parts.append(text)


class PageFetcher:
    def __init__(self, *, timeout: float = 10, max_bytes: int = 1_000_000):
        self.timeout = timeout
        self.max_bytes = max_bytes

    def fetch(self, url: str) -> dict:
        current_url = url.strip()
        for _ in range(4):
            self._validate_url(current_url)
            request = Request(
                current_url,
                headers={"User-Agent": "AI-Brain-Research/1.0", "Accept": "text/html,text/plain"},
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    final_url = response.geturl()
                    self._validate_url(final_url)
                    content_type = response.headers.get("Content-Type", "")
                    if "text/html" not in content_type.lower() and "text/plain" not in content_type.lower():
                        raise PageFetchError("The source URL did not return readable text.")
                    data = response.read(self.max_bytes + 1)
                    if len(data) > self.max_bytes:
                        raise PageFetchError("The source response exceeded the size limit.")
                    if response.headers.get("Content-Encoding"):
                        pass
            except UnsafeUrlError:
                raise
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                raise PageFetchError("The source page could not be fetched.") from exc

            if final_url != current_url and response.status in (301, 302, 303, 307, 308):
                current_url = urljoin(current_url, final_url)
                continue
            break
        else:
            raise PageFetchError("Too many redirects.")

        text = data.decode("utf-8", errors="replace")
        parser = _TextExtractor()
        if "text/html" in content_type.lower():
            parser.feed(text)
            title = " ".join(parser.title_parts).strip() or urlparse(final_url).netloc
            content = " ".join(parser.parts)
        else:
            title = urlparse(final_url).netloc
            content = text[:self.max_bytes]
        content = re.sub(r"\s+", " ", content).strip()[:50_000]
        return {
            "canonical_url": final_url,
            "title": title[:300],
            "domain": urlparse(final_url).netloc.lower(),
            "content": content,
            "published_at": None,
        }

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            raise UnsafeUrlError("Only HTTP and HTTPS source URLs are allowed.")
        if not parsed.hostname:
            raise UnsafeUrlError("The source URL has no valid hostname.")
        hostname = parsed.hostname.rstrip(".").lower()
        if hostname in ("localhost", "localhost.localdomain"):
            raise UnsafeUrlError("Local and loopback URLs are not allowed.")
        try:
            addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme.lower() == "https" else 80), type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise UnsafeUrlError("The source hostname could not be resolved safely.") from exc
        if not addresses:
            raise UnsafeUrlError("The source hostname resolved to no addresses.")
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                raise UnsafeUrlError("Private and internal source addresses are not allowed.")
