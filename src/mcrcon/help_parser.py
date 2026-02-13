"""Parse Minecraft server help output into command definitions for autocomplete.

Inspired by minecraft-fancy-rcon-cli's help_parser.rs. After connecting, the
REPL sends 'help' to the server and feeds the response through this module to
dynamically build the command completer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Regex patterns for parsing help output lines
_RE_CMD = re.compile(r"^/?(?P<cmd>\w[\w-]*)(?P<args>.*)")
_RE_REQUIRED = re.compile(r"<([^>]+)>")
_RE_OPTIONAL = re.compile(r"\[<([^>]+)>\]")
_RE_REQUIRED_CHOICE = re.compile(r"\(([^)]+\|[^)]+)\)")
_RE_OPTIONAL_CHOICE = re.compile(r"\[([^\]]+\|[^\]]+)\]")
_RE_ALIAS = re.compile(r"^/?(?P<alias>\w[\w-]*)\s*->\s*(?P<target>\w[\w-]*)")


@dataclass(frozen=True)
class Required:
    """A required positional argument like <player>."""

    name: str


@dataclass(frozen=True)
class Optional:
    """An optional argument like [<reason>]."""

    name: str


@dataclass(frozen=True)
class RequiredChoice:
    """A required choice like (grant|revoke)."""

    options: list[str]


@dataclass(frozen=True)
class OptionalChoice:
    """An optional choice like [survival|creative]."""

    options: list[str]


Argument = Required | Optional | RequiredChoice | OptionalChoice


def format_help_response(body: str) -> str:
    """Fix formatting of help output from the server.

    The server often concatenates lines, so we insert newlines before '/'
    characters that aren't at the start of a line to separate commands.
    """
    fixed = []
    prev = None
    for char in body:
        if char == "/" and prev is not None and prev != "\n":
            fixed.append("\n")
        fixed.append(char)
        prev = char
    return "".join(fixed).strip()


def parse_commands(help_text: str) -> dict[str, list[Argument]]:
    """Parse formatted help text into a mapping of command names to argument lists."""
    commands: dict[str, list[Argument]] = {}
    aliases: dict[str, str] = {}

    for raw_line in help_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Check for alias lines like "/msg -> tell"
        alias_match = _RE_ALIAS.match(line)
        if alias_match:
            alias = alias_match.group("alias")
            target = alias_match.group("target")
            aliases[alias] = target
            continue

        cmd_match = _RE_CMD.match(line)
        if not cmd_match:
            continue

        name = cmd_match.group("cmd")
        args_str = cmd_match.group("args")
        args = _parse_args(args_str)
        commands[name] = args

    # Resolve aliases: copy target's args to the alias
    for alias, target in aliases.items():
        if target in commands:
            commands[alias] = list(commands[target])

    return commands


def _parse_args(args_str: str) -> list[Argument]:
    """Parse the argument portion of a help line into typed Argument objects.

    Processes choices first, then removes them from the string before parsing
    positional args to avoid double-matching angle brackets inside choices.
    """
    args: list[Argument] = []

    # Parse required choices: (a|b|c)
    for match in _RE_REQUIRED_CHOICE.finditer(args_str):
        options = [s.strip() for s in match.group(1).split("|")]
        args.append(RequiredChoice(options=options))

    # Parse optional choices: [a|b|c]
    for match in _RE_OPTIONAL_CHOICE.finditer(args_str):
        options = [s.strip() for s in match.group(1).split("|")]
        args.append(OptionalChoice(options=options))

    # Remove choices from string before parsing positional args
    remaining = _RE_REQUIRED_CHOICE.sub("", args_str)
    remaining = _RE_OPTIONAL_CHOICE.sub("", remaining)

    # Parse optional args first: [<name>] (before required, to avoid matching
    # the inner <name> as a required arg)
    optional_names = set()
    for match in _RE_OPTIONAL.finditer(remaining):
        name = match.group(1)
        optional_names.add(name)
        args.append(Optional(name=name))

    # Remove optional args before parsing required args
    remaining = _RE_OPTIONAL.sub("", remaining)

    # Parse required args: <name>
    for match in _RE_REQUIRED.finditer(remaining):
        name = match.group(1)
        if name not in optional_names:
            args.append(Required(name=name))

    return args
