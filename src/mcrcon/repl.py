"""Interactive REPL using prompt_toolkit."""

from __future__ import annotations

import sys
import time

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory

from mcrcon.client import ConnectionError as RconConnectionError
from mcrcon.client import RconClient
from mcrcon.completer import MinecraftCompleter, build_completer
from mcrcon.config import HISTORY_FILE, ensure_config_dir
from mcrcon.formatting import format_response
from mcrcon.help_parser import format_help_response, parse_commands

MAX_RECONNECT_ATTEMPTS = 3


def run_repl(client: RconClient, password: str, *, color: bool = True) -> None:
    """Run the interactive REPL loop.

    Args:
        client: An already-connected and authenticated RconClient.
        password: The RCON password, stored for reconnection attempts.
        color: If True, convert formatting codes to ANSI. If False, strip them.
    """
    ensure_config_dir()

    # Build completer from server's help output
    completer = _build_completer_from_server(client)

    history = FileHistory(str(HISTORY_FILE))
    session: PromptSession[str] = PromptSession(
        history=history,
        completer=completer,
        complete_while_typing=False,
    )

    while True:
        try:
            text = session.prompt(HTML("<ansigreen>rcon</ansigreen>> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not text:
            continue

        if text in ("exit", "quit"):
            print("Goodbye.")
            break

        if text == "reconnect":
            if _reconnect(client, password):
                # Rebuild completer after reconnection
                new_completer = _build_completer_from_server(client)
                if new_completer is not None:
                    session.completer = new_completer
            continue

        _execute_command(client, password, text, session, color=color)


def _execute_command(
    client: RconClient,
    password: str,
    text: str,
    session: PromptSession[str],
    *,
    color: bool = True,
) -> None:
    """Execute a command, handling connection errors with auto-reconnect."""
    try:
        response = client.command(text)
        if response:
            print(format_response(response, color=color))
    except RconConnectionError:
        print("Connection lost. Attempting to reconnect...", file=sys.stderr)
        if _reconnect(client, password):
            new_completer = _build_completer_from_server(client)
            if new_completer is not None:
                session.completer = new_completer
            try:
                response = client.command(text)
                if response:
                    print(format_response(response, color=color))
            except RconConnectionError:
                print(
                    "Failed to execute command after reconnection.",
                    file=sys.stderr,
                )


def _build_completer_from_server(client: RconClient) -> MinecraftCompleter | None:
    """Query the server for help and build a completer from the response."""
    try:
        help_response = client.command("help")
        if help_response:
            formatted = format_help_response(help_response)
            commands = parse_commands(formatted)
            if commands:
                return build_completer(commands)
    except (ConnectionError, TimeoutError):
        print(
            "Warning: could not fetch help from server, autocomplete will be limited.",
            file=sys.stderr,
        )
    return None


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
