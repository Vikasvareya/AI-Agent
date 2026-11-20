import json
from threading import Lock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config.providers.openai_compatible_settings import (
    OpenAICompatibleSettings,
)
from app.providers.base_provider import BaseProvider, ProviderError
from app.utils.logger import get_logger


logger = get_logger("OpenAICompatibleProvider")


class OpenAICompatibleProvider(BaseProvider):
    def __init__(self, settings: OpenAICompatibleSettings):
        self.settings = settings
        self._models: list[dict[str, str]] = []
        self._models_loaded_at: float | None = None
        self._models_lock = Lock()

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    @property
    def default_model(self) -> str:
        return self.settings.model

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict | None = None,
        timeout: int | None = None,
    ) -> dict:
        headers = {"Accept": "application/json"}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.settings.base_url.rstrip('/')}/{path.lstrip('/')}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(
                request,
                timeout=timeout or self.settings.timeout,
            ) as response:
                try:
                    result = json.loads(response.read())
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ProviderError(
                        "The OpenAI-compatible provider returned invalid JSON."
                    ) from exc
        except HTTPError as exc:
            exc.close()
            raise ProviderError(
                "The OpenAI-compatible provider rejected the request "
                f"(HTTP {exc.code})."
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            logger.warning("OpenAI-compatible provider request failed.")
            raise ProviderError(
                "The configured OpenAI-compatible provider is unavailable."
            ) from exc

        if not isinstance(result, dict):
            raise ProviderError(
                "The OpenAI-compatible provider returned an invalid response."
            )
        return result

    def list_models(
        self,
        *,
        refresh: bool = False,
    ) -> list[dict[str, str]]:
        with self._models_lock:
            if (
                not refresh
                and self._models_loaded_at is not None
                and monotonic() - self._models_loaded_at < 30
            ):
                return [model.copy() for model in self._models]

            response = self._request_json("models")
            model_data = response.get("data")
            if not isinstance(model_data, list):
                raise ProviderError(
                    "The OpenAI-compatible provider returned an invalid model list."
                )
            models = []
            for item in model_data:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    model_id = item["id"]
                    models.append({
                        "id": model_id,
                        "name": item.get("name", model_id)
                            if isinstance(item.get("name"), str)
                            else model_id,
                        "provider": self.provider_name,
                    })
            self._models = sorted(models, key=lambda model: model["id"].lower())
            self._models_loaded_at = monotonic()
            return [model.copy() for model in self._models]

    def health_check(self, timeout: float = 2.0) -> bool:
        try:
            self._request_json("models", timeout=max(1, int(timeout)))
            return True
        except ProviderError:
            return False

    def ask(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        timeout: int | None = None,
    ) -> str:
        if timeout is not None and timeout <= 0:
            raise ValueError("Provider timeout must be greater than zero.")
        response = self._request_json(
            "chat/completions",
            method="POST",
            payload={"model": model or self.default_model, "messages": messages},
            timeout=timeout,
        )
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "The OpenAI-compatible provider returned an invalid chat response."
            ) from exc
        if not isinstance(content, str):
            raise ProviderError(
                "The OpenAI-compatible provider returned a non-text response."
            )
        return content
