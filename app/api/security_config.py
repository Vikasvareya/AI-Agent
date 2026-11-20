import ipaddress
import os


def read_boolean_env(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in ("1", "true", "yes"):
        return True
    if normalized in ("0", "false", "no"):
        return False
    raise ValueError(f"{name} must be set to true or false.")


def validate_api_auth(
    host: str,
    *,
    require_auth: bool,
    has_configured_token: bool,
) -> None:
    normalized_host = host.strip().lower().rstrip(".")
    is_loopback = normalized_host == "localhost"
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(normalized_host).is_loopback
        except ValueError:
            is_loopback = False

    if not require_auth and not is_loopback:
        raise ValueError(
            "AI_AGENT_REQUIRE_AUTH=true is required when the API binds "
            "to a non-loopback host."
        )
    if require_auth and not has_configured_token:
        raise ValueError(
            "Authentication is required, but no API, admin, or user token "
            "is configured."
        )
