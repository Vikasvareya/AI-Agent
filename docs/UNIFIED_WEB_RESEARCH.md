# Unified Web Research

## Providers

The research layer supports:

- Brave Search with `AI_AGENT_BRAVE_SEARCH_API_KEY`
- SearXNG with `SEARXNG_ENABLED=true` and `SEARXNG_BASE_URL`
- Automatic provider fallback in `SEARCH_PROVIDER=auto`
- Explicit `brave`, `searxng`, or `compare` modes

Search results are normalized, deduplicated by URL, and attributed to the
provider that supplied them. Empty results are valid and do not imply a
transport failure.

## Direct source fetching

`POST /v1/research/fetch` accepts a public HTTP/HTTPS URL and returns a bounded
text extraction. The fetcher blocks loopback, private, link-local, reserved,
multicast, and unspecified addresses, rechecks resolved addresses, limits
response size, and restricts content to HTML/plain text.

## Chat integration

ChatService can use the existing SearchManager for explicit and automatically
detected research. Automatic research remains gated by the existing freshness
rules. Normal chat and the Time/Calculator tools do not send unnecessary
search requests.

## API

- `GET /v1/research/status`
- `POST /v1/research/search`
- `POST /v1/research/fetch`

## Limitations

- SearXNG must be configured and reachable; it may aggregate upstream engines
  and is not an independent index.
- Direct fetching has no JavaScript rendering or CAPTCHA handling.
- Compare mode merges providers but cannot prove upstream engine independence.
