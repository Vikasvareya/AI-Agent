from threading import Lock
from time import monotonic
from urllib.error import URLError
from urllib.request import urlopen

from ollama import Client, ResponseError
from app.config.providers.ollama_settings import OllamaSettings
from app.providers.base_provider import BaseProvider, ProviderError
from app.utils.logger import get_logger


logger = get_logger("OllamaProvider")


class OllamaProvider(BaseProvider):
    """
    Ollama implementation of BaseProvider.
    """

    def __init__(self, settings: OllamaSettings):

        """
        Initialize the Ollama provider.

        Args:
            settings: Ollama configuration.
        """

        self.settings = settings
        self.model = settings.model
        self.client = Client(
            host=settings.host,
            timeout=settings.timeout,
        )
        self._models: list[dict[str, str]] = []
        self._models_loaded_at: float | None = None
        self._models_lock = Lock()

        logger.info(
            f"Ollama Provider initialized with model {self.model}"
        )

    @property
    def default_model(self) -> str:
        return self.model

    @property
    def provider_name(self) -> str:
        return "ollama"

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
            try:
                response = self.client.list()
                models = [
                    {
                        "id": item.model,
                        "name": item.model,
                        "provider": "ollama",
                    }
                    for item in response.models
                    if item.model
                ]
            except ResponseError as exc:
                raise ProviderError(
                    f"Ollama rejected the model-list request: {exc}"
                ) from exc
            except Exception as exc:
                logger.exception("Could not retrieve Ollama models")
                raise ProviderError(
                    "The configured Ollama service is unavailable."
                ) from exc
            self._models = sorted(models, key=lambda model: model["id"].lower())
            self._models_loaded_at = monotonic()
            return [model.copy() for model in self._models]

    def health_check(self, timeout: float = 2.0) -> bool:
        try:
            with urlopen(
                f"{self.settings.host.rstrip('/')}/",
                timeout=timeout,
            ) as response:
                return response.status == 200
        except (URLError, TimeoutError, OSError):
            return False

    def ask(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        timeout: int | None = None,
    ) -> str:
        selected_model = model or self.model
        if timeout is not None and timeout <= 0:
            raise ValueError("Provider timeout must be greater than zero.")
        client = (
            self.client
            if timeout is None or timeout == self.settings.timeout
            else Client(
                host=self.settings.host,
                timeout=timeout,
            )
        )
        close_client = client is not self.client
        logger.info(f"Sending prompt to {selected_model}")

        try:
            response = client.chat(
                model=selected_model,
                messages=messages,
            )

            logger.info("Response received successfully")

            return response["message"]["content"]

        except ResponseError as e:
            logger.error(f"Ollama Response Error: {e}")
            raise ProviderError(
                f"Ollama rejected the request: {e}"
            ) from e

        except Exception as exc:
            logger.exception("Unexpected Error")
            raise ProviderError(
                "The configured Ollama service is unavailable."
            ) from exc
        finally:
            if close_client:
                client.close()