from dataclasses import dataclass


@dataclass(frozen=True)
class BaseProviderSettings:
    """
    Base configuration shared by all AI providers.

    This class contains only the settings that are common across
    multiple providers.
    """

    model: str
    timeout: int