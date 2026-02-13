"""Parse Minecraft server help output into command definitions for autocomplete.

Handles the Bukkit/Spigot paginated help system. The REPL sends '?' to get
the help index, fetches all pages, then queries individual commands with
'? <command>' for detailed usage and alias information.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# Regex patterns for parsing help output lines
_RE_CMD = re.compile(r"^/?(?P<cmd>\w[\w-]*)(?P<args>.*)")
_RE_ALIAS = re.compile(r"^/?(?P<alias>\w[\w-]*)\s*->\s*(?P<target>\w[\w-]*)")

# Patterns for the paginated help format
_RE_HELP_HEADER = re.compile(r"^-+\s*Help:")
_RE_PAGE_COUNT = re.compile(r"\((\d+)/(\d+)\)")
_RE_INDEX_ENTRY = re.compile(r"^/(?P<cmd>[^:\s]+(?::[^:\s]+)*):\s+(?P<desc>.+)")
_RE_CATEGORY_ENTRY = re.compile(r"^\w[\w-]*:\s*(All commands for |Lists )")
_RE_META_LINE = re.compile(r"^Use /help ")


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


@dataclass
class CommandHelp:
    """Parsed detailed help for a single command."""

    usage_args: list[Argument] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


def parse_page_count(text: str) -> int:
    """Extract the total page count from a help index header.

    Looks for a pattern like '(1/58)' in the header line and returns the
    total (58). Returns 1 if no page count is found.
    """
    match = _RE_PAGE_COUNT.search(text)
    if match:
        return int(match.group(2))
    return 1


def parse_help_index(text: str) -> list[str]:
    """Parse a help index page and return command names.

    Extracts command names from lines like '/command: description' and
    '/namespace:command: description'. Skips header lines, category entries,
    and meta lines.
    """
    commands: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Skip header lines like '--------- Help: Index (1/58) ----'
        if _RE_HELP_HEADER.match(line):
            continue

        # Skip category entries like 'Minecraft: All commands for Minecraft'
        if _RE_CATEGORY_ENTRY.match(line):
            continue

        # Skip meta lines like 'Use /help [n] to get page n of help.'
        if _RE_META_LINE.match(line):
            continue

        # Match command entries like '/command: description'
        entry_match = _RE_INDEX_ENTRY.match(line)
        if entry_match:
            commands.append(entry_match.group("cmd"))
        else:
            log.debug("Unmatched index line: %r", line)

    return commands


def parse_command_help(text: str) -> CommandHelp | None:
    """Parse the detailed help output for a single command.

    Expects output from '? <command>' like:
        --------- Help: /teleport -----------------------------
        Alias for /tp
        Description: Teleport to a player.
        Usage: /tp <player> [otherplayer]
        Aliases: tele, etele, teleport, eteleport, etp, tp2p, etp2p

    Returns None if the text contains no parseable help.
    """
    usage_args: list[Argument] = []
    aliases: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Skip the header line
        if _RE_HELP_HEADER.match(line):
            continue

        # Parse Usage line
        if line.startswith("Usage:"):
            usage_str = line[len("Usage:") :].strip()
            # The usage line includes the command name, so strip it
            # Strip the command name before parsing args
            cmd_match = re.match(r"^/?[\w:.-]+\s*(.*)", usage_str)
            if cmd_match:
                usage_args = _parse_args(cmd_match.group(1))
            continue

        # Parse Aliases line
        if line.startswith("Aliases:"):
            aliases_str = line[len("Aliases:") :].strip()
            aliases = [a.strip() for a in aliases_str.split(",") if a.strip()]
            continue

    if not usage_args and not aliases:
        log.debug("parse_command_help: no usage or aliases found")
        return None

    log.debug(
        "parse_command_help: %d args, %d aliases",
        len(usage_args),
        len(aliases),
    )
    return CommandHelp(usage_args=usage_args, aliases=aliases)


def parse_player_list(text: str) -> list[str]:
    """Parse the output of the 'online' command into a list of player names.

    Expected format:
        There are 2 out of maximum 20 players online.
        default: Player1, Player2
        admin: Player3
    """
    players: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Skip the summary line
        if line.startswith(("There are ", "There is ")):
            continue

        # Parse 'group: player1, player2' lines
        if ":" in line:
            _, _, names_part = line.partition(":")
            for raw_name in names_part.split(","):
                stripped = raw_name.strip()
                if stripped:
                    players.append(stripped)

    return players


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


# Single combined pattern that matches all argument types in one left-to-right
# pass. Alternatives are ordered so longer/more-specific patterns match first
# (e.g. [<name>] before [name] before <name>).
_RE_ARG = re.compile(
    r"\((?P<req_choice>[^)]+\|[^)]+)\)"  # Required choice: (a|b|c)
    r"|\[(?P<opt_bracket><[^>]+>)\]"  # Optional bracketed: [<name>]
    r"|\[(?P<opt_choice>[^\]]+\|[^\]]+)\]"  # Optional choice: [a|b|c]
    r"|\[(?P<opt_bare>\w+)\]"  # Optional bare: [name]
    r"|<(?P<required>[^>]+)>"  # Required: <name>
)


def _parse_args(args_str: str) -> list[Argument]:
    """Parse the argument portion of a help line into typed Argument objects.

    Uses a single left-to-right regex scan to match all argument types at once,
    so ordering is always correct by construction.
    """
    args: list[Argument] = []

    for match in _RE_ARG.finditer(args_str):
        if match.group("req_choice") is not None:
            options = [s.strip() for s in match.group("req_choice").split("|")]
            args.append(RequiredChoice(options=options))
        elif match.group("opt_bracket") is not None:
            # Strip the angle brackets from <name>
            name = match.group("opt_bracket")[1:-1]
            args.append(Optional(name=name))
        elif match.group("opt_choice") is not None:
            options = [s.strip() for s in match.group("opt_choice").split("|")]
            args.append(OptionalChoice(options=options))
        elif match.group("opt_bare") is not None:
            args.append(Optional(name=match.group("opt_bare")))
        elif match.group("required") is not None:
            args.append(Required(name=match.group("required")))

    return args
