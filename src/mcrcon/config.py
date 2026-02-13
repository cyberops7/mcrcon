"""Configuration loading for the RCON client."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "mcrcon"
CONFIG_FILE = CONFIG_DIR / "config.toml"
HISTORY_FILE = CONFIG_DIR / "history"
CACHE_DIR = CONFIG_DIR / "cache"


@dataclass(frozen=True)
class CredentialConfig:
    """1Password credential reference for a server."""

    vault: str
    item: str
    field: str


@dataclass(frozen=True)
class ServerConfig:
    """Configuration for a single Minecraft server."""

    name: str
    host: str
    port: int = 25575
    credentials: CredentialConfig | None = None

    def resolve_credentials(
        self, default_credentials: CredentialConfig | None
    ) -> CredentialConfig | None:
        """Return the effective credentials, falling back to the default."""
        return self.credentials or default_credentials


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    default_server: str | None
    default_credentials: CredentialConfig | None
    servers: dict[str, ServerConfig]


def load_config(path: Path = CONFIG_FILE) -> AppConfig:
    """Load and parse the configuration file.

    Returns hardcoded defaults if no config file exists.
    """
    if not path.exists():
        return _default_config()

    with path.open("rb") as f:
        raw = tomllib.load(f)

    defaults = raw.get("defaults", {})
    default_server = defaults.get("server")
    default_credentials = _parse_credentials(defaults.get("credentials"))

    servers: dict[str, ServerConfig] = {}
    for key, val in raw.get("servers", {}).items():
        servers[key] = ServerConfig(
            name=val.get("name", key),
            host=val["host"],
            port=val.get("port", 25575),
            credentials=_parse_credentials(val.get("credentials")),
        )

    return AppConfig(
        default_server=default_server,
        default_credentials=default_credentials,
        servers=servers,
    )


def _parse_credentials(raw: dict | None) -> CredentialConfig | None:
    """Parse a credentials section from the config file."""
    if raw is None:
        return None
    return CredentialConfig(
        vault=raw["vault"],
        item=raw["item"],
        field=raw["field"],
    )


def _default_config() -> AppConfig:
    """Return the hardcoded default configuration."""
    default_creds = CredentialConfig(
        vault="Skynet",
        item="minecraft",
        field="RCON_PASSWORD",
    )
    return AppConfig(
        default_server="mc-1",
        default_credentials=default_creds,
        servers={
            "mc-1": ServerConfig(
                name="MC-1 (Java + Bedrock)",
                host="10.0.0.112",
            ),
            "mc-3": ServerConfig(
                name="MC-3 (Java + Bedrock)",
                host="10.0.0.114",
            ),
        },
    )


def ensure_config_dir() -> None:
    """Create the config and cache directories if they do not exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
