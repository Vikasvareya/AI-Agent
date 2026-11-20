from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlsplit

from app.config.providers.base_provider_settings import BaseProviderSettings


@dataclass(frozen=True)
class OpenAICompatibleSettings(BaseProviderSettings):
    base_url: str
    api_key: str | None = None

    def __post_init__(self) -> None:
        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "OpenAI-compatible base URL must be an HTTP(S) URL without "
                "credentials, query, or fragment."
            )
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError(
                "OpenAI-compatible base URL must use a valid port."
            ) from exc
        if not self.model.strip():
            raise ValueError("OpenAI-compatible model must not be empty.")
        if self.timeout <= 0:
            raise ValueError("Provider timeout must be greater than zero.")
        if self.api_key and parsed.scheme != "https":
            try:
                is_loopback = ip_address(parsed.hostname).is_loopback
            except ValueError:
                is_loopback = parsed.hostname.lower() == "localhost"
            if not is_loopback:
                raise ValueError(
                    "OpenAI-compatible API keys require HTTPS except for "
                    "localhost services."
                )
