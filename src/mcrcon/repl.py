"""Interactive REPL using prompt_toolkit."""

from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings

if TYPE_CHECKING:
    from prompt_toolkit.key_binding.key_processor import KeyPressEvent

from mcrcon.client import ConnectionError as RconConnectionError
from mcrcon.client import RconClient
from mcrcon.completer import MinecraftCompleter
from mcrcon.config import HISTORY_FILE, ensure_config_dir
from mcrcon.formatting import format_response
from mcrcon.help_fetcher import (
    fetch_all_help,
    fetch_player_list,
    load_cache,
    save_cache,
)

log = logging.getLogger(__name__)

MAX_RECONNECT_ATTEMPTS = 3
_PLAYER_REFRESH_INTERVAL = 60


def _create_key_bindings() -> KeyBindings:
    """Create custom key bindings for the REPL.

    Ctrl+C and Ctrl+D behavior:
    - If the current line has text, abandon it (show but don't execute) and start fresh
    - If the current line is empty, exit the application
    """
    kb = KeyBindings()

    @kb.add("c-c")
    def _(event: KeyPressEvent) -> None:
        """Handle Ctrl+C: abandon line if non-empty, exit if empty."""
        buffer = event.app.current_buffer
        if buffer.text:
            # Abandon the current line - insert newline and reset buffer
            print()  # Move to next line
            buffer.reset()
            event.app.renderer.reset()  # Force prompt redraw
        else:
            # Exit the application
            event.app.exit(exception=KeyboardInterrupt)

    @kb.add("c-d")
    def _(event: KeyPressEvent) -> None:
        """Handle Ctrl+D: abandon line if non-empty, exit if empty."""
        buffer = event.app.current_buffer
        if buffer.text:
            # Abandon the current line - insert newline and reset buffer
            print()  # Move to next line
            buffer.reset()
            event.app.renderer.reset()  # Force prompt redraw
        else:
            # Exit the application
            event.app.exit(exception=EOFError)

    return kb


@dataclass(frozen=True)
class _ServerInfo:
    """Connection details needed to create a background RCON client."""

    host: str
    port: int
    password: str
    timeout: float


def run_repl(  # noqa: PLR0913
    client: RconClient,
    password: str,
    *,
    host: str,
    port: int,
    timeout: float = 10.0,
    color: bool = True,
    raw: bool = False,
) -> None:
    """Run the interactive REPL loop.

    Args:
        client: An already-connected and authenticated RconClient.
        password: The RCON password, stored for reconnection attempts.
        host: Server hostname, used for the background refresh connection.
        port: Server port, used for the background refresh connection.
        timeout: Socket timeout for the background connection.
        color: If True, convert formatting codes to ANSI. If False, strip them.
        raw: If True, show raw output with formatting codes visible.
    """
    ensure_config_dir()

    server = _ServerInfo(host, port, password, timeout)
    completer = _init_completer(server)

    history = FileHistory(str(HISTORY_FILE))
    key_bindings = _create_key_bindings()
    session: PromptSession[str] = PromptSession(
        history=history,
        completer=completer,
        complete_while_typing=False,
        key_bindings=key_bindings,
    )

    while True:
        try:
            text = session.prompt(
                HTML("<ansigreen>rcon</ansigreen>> "),
            ).strip()
        except EOFError, KeyboardInterrupt:
            print("\nGoodbye.")
            break

        if not text:
            continue

        if text in ("exit", "quit"):
            print("Goodbye.")
            break

        if text == "reconnect":
            if _reconnect(client, password):
                _start_background_refresh(server, completer)
            continue

        _execute_command(client, text, server, completer, color=color, raw=raw)


def _execute_command(  # noqa: PLR0913
    client: RconClient,
    text: str,
    server: _ServerInfo,
    completer: MinecraftCompleter,
    *,
    color: bool = True,
    raw: bool = False,
) -> None:
    """Execute a command, handling connection errors with auto-reconnect."""
    try:
        response = client.command(text)
        if response:
            print(format_response(response, color=color, raw=raw))
    except RconConnectionError:
        print("Connection lost. Attempting to reconnect...", file=sys.stderr)
        if _reconnect(client, server.password):
            _start_background_refresh(server, completer)
            try:
                response = client.command(text)
                if response:
                    print(format_response(response, color=color, raw=raw))
            except RconConnectionError:
                print(
                    "Failed to execute command after reconnection.",
                    file=sys.stderr,
                )


def _init_completer(server: _ServerInfo) -> MinecraftCompleter:
    """Create a completer, load cache if available, and start background refresh."""
    completer = MinecraftCompleter({})

    cached = load_cache(server.host, server.port)
    if cached:
        completer.update_commands(cached)

    _start_background_refresh(server, completer)

    return completer


def _start_background_refresh(
    server: _ServerInfo,
    completer: MinecraftCompleter,
) -> None:
    """Start a daemon thread to refresh help data and player list."""
    thread = threading.Thread(
        target=_background_refresh,
        args=(server, completer),
        daemon=True,
    )
    thread.start()


def _background_refresh(
    server: _ServerInfo,
    completer: MinecraftCompleter,
) -> None:
    """Fetch help and player data in the background using a separate connection."""
    bg_client = RconClient(server.host, server.port, timeout=server.timeout)
    try:
        bg_client.connect()
        bg_client.authenticate(server.password)

        # Fetch the player list first (quick, single command)
        try:
            players = fetch_player_list(bg_client)
            completer.update_players(players)
        except Exception:  # noqa: BLE001
            log.debug("Failed to fetch player list", exc_info=True)

        # Fetch all help pages and detailed command help (slow)
        try:
            commands = fetch_all_help(bg_client)
            completer.update_commands(commands)
            save_cache(server.host, server.port, commands)
        except Exception:  # noqa: BLE001
            log.debug("Failed to fetch help data", exc_info=True)

        # Periodically refresh the player list
        while True:
            time.sleep(_PLAYER_REFRESH_INTERVAL)
            players = fetch_player_list(bg_client)
            completer.update_players(players)
    except Exception:  # noqa: BLE001
        log.debug("Background refresh stopped", exc_info=True)
    finally:
        bg_client.close()


def _reconnect(client: RconClient, password: str) -> bool:
    """Attempt to reconnect with exponential backoff.

    Returns True if reconnection succeeded.
    """
    client.close()
    for attempt in range(MAX_RECONNECT_ATTEMPTS):
        delay = 2**attempt
        print(
            f"Reconnecting in {delay}s "
            f"(attempt {attempt + 1}/{MAX_RECONNECT_ATTEMPTS})..."
        )
        time.sleep(delay)
        try:
            client.connect()
            client.authenticate(password)
        except Exception:  # noqa: BLE001, S112
            continue
        else:
            print("Reconnected successfully.")
            return True

    print(
        "Failed to reconnect. Use 'reconnect' to try again, or 'exit' to quit.",
        file=sys.stderr,
    )
    return False
