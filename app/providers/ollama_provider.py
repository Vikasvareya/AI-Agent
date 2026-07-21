from ollama import chat, ResponseError
from app.config.providers.ollama_settings import OllamaSettings
from app.providers.base_provider import BaseProvider
from app.utils.logger import logger


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

        logger.info(
            f"Ollama Provider initialized with model {self.model}"
        )

    def ask(self, messages: list[dict[str, str]]) -> str:
        logger.info(f"Sending prompt to {self.model}")

        try:
            response = chat(
                model=self.model,
                messages=messages,
            )

            logger.info("Response received successfully")

            return response["message"]["content"]

        except ResponseError as e:
            logger.error(f"Ollama Response Error: {e}")
            return f"Ollama Error: {e}"

        except Exception:
            logger.exception("Unexpected Error")
            return "Sorry, something went wrong."