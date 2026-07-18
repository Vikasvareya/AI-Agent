import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """
    Application configuration.

    Reads values from the .env file.
    """

    AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama")

    OLLAMA_MODEL = os.getenv(
        "OLLAMA_MODEL",
        "qwen3:4b"
    )

    TEMPERATURE = float(
        os.getenv("TEMPERATURE", 0.7)
    )

    TIMEOUT = int(
        os.getenv("TIMEOUT", 60)
    )


settings = Settings()