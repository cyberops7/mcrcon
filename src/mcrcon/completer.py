"""Minecraft command completer for prompt_toolkit.

Builds a dynamic completer from parsed help output, providing command name
completion, argument-level completion for choices, and player name completion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.completion import Completer, Completion

from mcrcon.help_parser import (
    Argument,
    Optional,
    OptionalChoice,
    Required,
    RequiredChoice,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

# Local REPL commands that are not sent to the server
LOCAL_COMMANDS = {"exit", "quit", "reconnect"}

# Argument names that indicate a player name is expected
_PLAYER_ARG_NAMES = {"player", "players", "target", "targets", "playername", "name"}


class MinecraftCompleter(Completer):
    """Completer that provides Minecraft command and argument completions.

    Supports dynamic updates to commands and player lists from background
    threads. Reference assignments are atomic under the GIL, so updates
    are thread-safe without explicit locking.
    """

    def __init__(self, commands: dict[str, list[Argument]]) -> None:
        self.commands = commands
        self.players: list[str] = []

    def update_commands(self, commands: dict[str, list[Argument]]) -> None:
        """Replace the commands dict atomically."""
        self.commands = commands

    def update_players(self, players: list[str]) -> None:
        """Replace the player list atomically."""
        self.players = players

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,  # noqa: ARG002
    ) -> Iterable[Completion]:
        """Yield completions based on the current input."""
        text = document.text_before_cursor
        words = text.split()

        # If text ends with a space, the user is starting a new word
        typing_new_word = text.endswith(" ") if text else True

        if not words or (len(words) == 1 and not typing_new_word):
            # Complete command name
            prefix = words[0] if words else ""
            yield from self._complete_command(prefix)
            return

        # Complete arguments for the current command
        cmd = words[0]
        if cmd not in self.commands:
            return

        args = self.commands[cmd]
        # Determine which argument position we're completing
        # words[0] is the command, so argument index is len(words) - 2
        # unless we're typing a new word, then it is len(words) - 1
        if typing_new_word:
            arg_index = len(words) - 1
            prefix = ""
        else:
            arg_index = len(words) - 2
            prefix = words[-1]

        if arg_index < len(args):
            yield from self._complete_argument(args[arg_index], prefix)
        elif not args:
            # No argument metadata (index-only, no detailed help yet).
            # Offer player names as a fallback.
            yield from self._complete_players(prefix)

    def _complete_command(self, prefix: str) -> Iterable[Completion]:
        """Yield command name completions matching the prefix."""
        prefix_lower = prefix.lower()

        for cmd in sorted(self.commands):
            if cmd.lower().startswith(prefix_lower):
                yield Completion(cmd, start_position=-len(prefix))

        for cmd in sorted(LOCAL_COMMANDS):
            if cmd.startswith(prefix_lower):
                yield Completion(cmd, start_position=-len(prefix))

    def _complete_argument(self, arg: Argument, prefix: str) -> Iterable[Completion]:
        """Yield argument completions for choice-type and player-type arguments."""
        if isinstance(arg, RequiredChoice | OptionalChoice):
            prefix_lower = prefix.lower()
            for option in arg.options:
                if option.lower().startswith(prefix_lower):
                    yield Completion(option, start_position=-len(prefix))
        elif (
            isinstance(arg, Required | Optional)
            and arg.name.lower() in _PLAYER_ARG_NAMES
        ):
            yield from self._complete_players(prefix)

    def _complete_players(self, prefix: str) -> Iterable[Completion]:
        """Yield player name completions matching the prefix."""
        prefix_lower = prefix.lower()
        for player in sorted(self.players):
            if player.lower().startswith(prefix_lower):
                yield Completion(player, start_position=-len(prefix))


def build_completer(commands: dict[str, list[Argument]]) -> MinecraftCompleter:
    """Build a completer from parsed help output."""
    return MinecraftCompleter(commands)
