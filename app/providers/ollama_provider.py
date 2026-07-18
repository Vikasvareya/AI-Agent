from ollama import chat, ResponseError
from app.config.settings import settings
from app.providers.base_provider import BaseProvider
from app.utils.logger import logger


class OllamaProvider(BaseProvider):
    """
    Ollama implementation of BaseProvider.
    """

    def __init__(self, model: str | None = None):
        self.model = model or settings.OLLAMA_MODEL

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