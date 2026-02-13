"""Fetch help data from the server and manage the on-disk cache.

Provides functions to fetch all paginated help pages and individual command
details, as well as the online player list. Help data is cached per-server
to allow instant completions on subsequent startups.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from mcrcon.config import CACHE_DIR
from mcrcon.formatting import strip_formatting
from mcrcon.help_parser import (
    Argument,
    Optional,
    OptionalChoice,
    Required,
    RequiredChoice,
    parse_command_help,
    parse_help_index,
    parse_page_count,
    parse_player_list,
)

if TYPE_CHECKING:
    from pathlib import Path

    from mcrcon.client import RconClient

log = logging.getLogger(__name__)

_CACHE_VERSION = 1


def cache_path(host: str, port: int) -> Path:
    """Return the cache file path for a server."""
    return CACHE_DIR / f"{host}_{port}.json"


def load_cache(host: str, port: int) -> dict[str, list[Argument]] | None:
    """Load cached commands from disk.

    Returns None if the cache doesn't exist or is corrupt.
    """
    path = cache_path(host, port)
    if not path.exists():
        log.debug("No cache file at %s", path)
        return None

    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError, KeyError, TypeError:
        log.debug("Corrupt cache file %s, ignoring", path, exc_info=True)
        return None

    if raw.get("version") != _CACHE_VERSION:
        log.debug("Cache version mismatch in %s", path)
        return None
    commands = _deserialize_commands(raw.get("commands", {}))
    log.debug("Loaded %d commands from cache %s", len(commands), path)
    return commands


def save_cache(host: str, port: int, commands: dict[str, list[Argument]]) -> None:
    """Serialize commands to JSON and write to the cache file.

    Skips writing if the commands dict is empty to avoid overwriting
    a good cache with empty data due to a fetch failure.
    """
    if not commands:
        log.debug("Skipping cache save: no commands to write")
        return

    path = cache_path(host, port)
    data = {
        "version": _CACHE_VERSION,
        "commands": _serialize_commands(commands),
    }
    path.write_text(json.dumps(data))
    log.debug("Saved %d commands to cache %s", len(commands), path)


def fetch_all_help(client: RconClient) -> dict[str, list[Argument]]:
    """Fetch all help pages and individual command details from the server.

    Sends '?' to get the first index page and page count, then fetches all
    remaining pages. For each unique command found, fetches detailed help
    with '? <command>' to get argument structure and aliases.
    """
    # Fetch the first page to get the total page count.
    # Strip Minecraft formatting codes (§x) before parsing.
    first_page = strip_formatting(client.command("?"))
    log.debug(
        "First help page (%d chars):\n%s",
        len(first_page),
        first_page,
    )

    total_pages = parse_page_count(first_page)
    all_command_names = parse_help_index(first_page)
    log.debug(
        "Page 1/%d: parsed %d commands: %s",
        total_pages,
        len(all_command_names),
        all_command_names,
    )

    # Fetch remaining pages
    for page_num in range(2, total_pages + 1):
        page_text = strip_formatting(client.command(f"? {page_num}"))
        page_commands = parse_help_index(page_text)
        log.debug(
            "Page %d/%d: parsed %d commands: %s",
            page_num,
            total_pages,
            len(page_commands),
            page_commands,
        )
        all_command_names.extend(page_commands)

    log.debug(
        "Total commands from index: %d unique names",
        len(all_command_names),
    )

    # Group all full names by their bare name (without namespace prefix)
    # so we only fetch detailed help once per unique command
    bare_to_full: dict[str, list[str]] = {}
    for full_name in all_command_names:
        bare = full_name.split(":", 1)[1] if ":" in full_name else full_name
        bare_to_full.setdefault(bare, []).append(full_name)

    log.debug(
        "Unique bare commands to fetch details for: %d",
        len(bare_to_full),
    )

    # Fetch detailed help for each unique bare command name
    commands: dict[str, list[Argument]] = {}

    for bare_name, full_names in bare_to_full.items():
        # Always query with the bare name for better help output
        detail_text = strip_formatting(client.command(f"? {bare_name}"))
        detail = parse_command_help(detail_text)

        if detail:
            args = detail.usage_args
            log.debug(
                "? %s: %d args, %d aliases %s",
                bare_name,
                len(args),
                len(detail.aliases),
                detail.aliases,
            )
            # Register aliases with the same args
            for alias in detail.aliases:
                commands[alias] = args
        else:
            args = []
            log.debug("? %s: no parseable help", bare_name)

        # Store under the bare name and all namespaced variants
        commands[bare_name] = args
        for full_name in full_names:
            commands[full_name] = args

    log.debug("Final command count: %d", len(commands))
    return commands


def fetch_player_list(client: RconClient) -> list[str]:
    """Fetch the current online player list from the server."""
    response = strip_formatting(client.command("online"))
    players = parse_player_list(response)
    log.debug("Player list (%d): %s", len(players), players)
    return players


def _serialize_commands(commands: dict[str, list[Argument]]) -> dict[str, Any]:
    """Serialize a commands dict to a JSON-compatible structure."""
    result: dict[str, Any] = {}
    for name, args in commands.items():
        result[name] = [_serialize_arg(arg) for arg in args]
    return result


def _serialize_arg(arg: Argument) -> dict[str, Any]:
    """Serialize a single Argument to a JSON-compatible dict."""
    if isinstance(arg, Required):
        return {"type": "Required", "name": arg.name}
    if isinstance(arg, Optional):
        return {"type": "Optional", "name": arg.name}
    if isinstance(arg, RequiredChoice):
        return {"type": "RequiredChoice", "options": arg.options}
    if isinstance(arg, OptionalChoice):
        return {"type": "OptionalChoice", "options": arg.options}
    msg = f"Unknown argument type: {type(arg)}"
    raise TypeError(msg)


def _deserialize_commands(raw: dict[str, Any]) -> dict[str, list[Argument]]:
    """Deserialize a JSON structure back into a commands dict."""
    commands: dict[str, list[Argument]] = {}
    for name, raw_args in raw.items():
        commands[name] = [_deserialize_arg(a) for a in raw_args]
    return commands


def _deserialize_arg(raw: dict[str, Any]) -> Argument:
    """Deserialize a single JSON dict back into an Argument."""
    arg_type = raw["type"]
    if arg_type == "Required":
        return Required(name=raw["name"])
    if arg_type == "Optional":
        return Optional(name=raw["name"])
    if arg_type == "RequiredChoice":
        return RequiredChoice(options=raw["options"])
    if arg_type == "OptionalChoice":
        return OptionalChoice(options=raw["options"])
    msg = f"Unknown argument type: {arg_type}"
    raise ValueError(msg)
