# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`mcrcon` is an interactive Minecraft RCON (Remote Console) CLI client built with Python. It provides a rich REPL experience for managing Minecraft servers remotely via the RCON protocol.

## Development Commands

### Environment Management
- **Install dependencies**: `uv sync`
- **Add a new dependency**: `uv add <package>`
- **Run the CLI**: `uv run mcrcon [server]`

### Testing and Quality
- **Run all tests**: `uv run pytest`
- **Run specific test file**: `uv run pytest tests/test_protocol.py`
- **Run specific test function**: `uv run pytest tests/test_protocol.py::test_encode_packet`
- **Lint and format check**: `uv run ruff check .`
- **Auto-fix linting issues**: `uv run ruff check --fix .`
- **Format code**: `uv run ruff format .`

## Architecture

### Protocol Layer (`protocol.py`)
Handles the low-level Minecraft RCON wire protocol encoding/decoding. Key concepts:
- **Packet structure**: `[length:i32][request_id:i32][type:i32][payload\0\0]`
- **Packet types**: LOGIN (3), COMMAND (2), RESPONSE (0)
- The `Packet` dataclass provides `encode()` and `decode()` methods

### Client Layer (`client.py`)
Manages TCP connections and command/response flow. Key patterns:
- **Sentinel technique**: For multi-packet responses, sends a follow-up empty packet with `_SENTINEL_ID=9999`. The client collects all responses until the sentinel response arrives, ensuring complete multi-packet responses are captured
- **Auto-reconnection**: Connection errors trigger automatic reconnect with exponential backoff
- **Request ID counter**: Uses `itertools.count(1)` to generate unique request IDs

### REPL Layer (`repl.py`)
Interactive prompt using `prompt_toolkit`. Features:
- **Dynamic autocomplete**: Background thread fetches help data using `?` command and the online player list
- **Cache-first startup**: Loads cached help from `~/.config/mcrcon/cache/` for instant completions, then refreshes in the background
- **Background refresh**: Uses a separate `RconClient` connection (via `_ServerInfo` dataclass) to avoid socket contention with the main REPL
- **Player list refresh**: Periodically refreshes the online player list (every 60s) for player name completions
- **History**: Stores command history in `~/.config/mcrcon/history`
- **Auto-reconnect**: On connection loss, attempts reconnection with exponential backoff (max 3 attempts)
- **Special commands**: `exit`, `quit`, `reconnect` (handled locally, not sent to server)

### Configuration System (`config.py`)
- **Config location**: `~/.config/mcrcon/config.toml`
- **Cache location**: `~/.config/mcrcon/cache/` (per-server JSON files)
- **Credential integration**: Uses 1Password CLI (`op`) to retrieve RCON passwords
- **Fallback defaults**: Hardcoded defaults in `_default_config()` if no config file exists
- **Credential resolution**: Per-server credentials override default credentials

### Help Parser (`help_parser.py`)
Parses Minecraft server help output to build dynamic autocompletions:
- **Argument types**: `Required`, `Optional`, `RequiredChoice`, `OptionalChoice`, `CommandHelp`
- **Paginated help**: `parse_page_count()` extracts total pages from the `(1/58)` header
- **Index parsing**: `parse_help_index()` extracts command names from index pages, handling namespaced commands (e.g., `minecraft:teleport`) and skipping categories
- **Detailed help**: `parse_command_help()` parses individual command help (Usage, Aliases)
- **Player list**: `parse_player_list()` parses the `online` command output (`group: player1, player2`)
- **Single-pass arg parsing**: `_parse_args()` uses a combined regex (`_RE_ARG`) that matches all argument types in one left-to-right scan, so ordering is correct by construction
- **Bare optional args**: Handles `[name]` format (without angle brackets) in addition to `[<name>]`

### Help Fetcher (`help_fetcher.py`)
Fetches help data from the server and manages the on-disk cache:
- **Formatting code stripping**: All `client.command()` responses are passed through `strip_formatting()` before parsing, since Bukkit/Spigot servers embed `§x` color codes in help output
- **Paginated fetching**: Sends `?` for page 1, `? N` for subsequent pages to collect all commands
- **Detailed help**: Sends `? <command>` for each unique command to get usage args and aliases
- **Namespace deduplication**: Groups namespaced variants (e.g., `minecraft:teleport` and `teleport`) to avoid redundant queries
- **Cache format**: JSON with version number, stores serialized `Argument` types per command
- **Serialization**: Bidirectional JSON serialization for all `Argument` types
- **Debug logging**: Extensive `log.debug()` tracing at every pipeline stage (page counts, parsed commands, detail results, cache operations)

### Completer (`completer.py`)
Provides intelligent autocomplete using parsed help data:
- **Command completion**: Completes command names (case-insensitive)
- **Argument completion**: Completes choice-type arguments (e.g., `(grant|revoke)`)
- **Player name completion**: Completes player names for arguments named `player`, `target`, `targets`, etc.
- **Fallback completion**: When no argument metadata exists (index-only), offers player names for any argument position
- **Dynamic updates**: `update_commands()` and `update_players()` allow thread-safe atomic replacement
- **Position-aware**: Tracks which argument position is being completed

### Credentials (`credentials.py`)
Integrates with 1Password CLI to securely retrieve RCON passwords:
- **Required tool**: `op` CLI must be installed and authenticated
- **Timeout**: 30-second timeout for credential retrieval
- **Validation**: Ensures retrieved password is non-empty

### Formatting (`formatting.py`)
Handles Minecraft color and formatting codes in server responses:
- **Default behavior**: Converts formatting codes to ANSI terminal escape sequences (colors, bold, italic, underline, strikethrough)
- **RGB support**: 24-bit RGB colors (`§x§R§R§G§G§B§B`) are converted using `\033[38;2;r;g;bm` sequences
- **Legacy colors**: `§0-f` mapped to standard/bright ANSI foreground colors
- **Obfuscated (§k)**: Stripped silently (no terminal equivalent)
- **Reset safety**: A trailing ANSI reset is appended whenever formatting codes are present
- **No-color mode**: `--no-color` CLI flag falls back to stripping all codes
- **Key functions**: `convert_formatting()` for ANSI output, `strip_formatting()` for plain text, `format_response()` dispatches based on `color` flag

## Testing Architecture

### Test Structure
- `conftest.py`: Currently minimal, provides common test setup
- Each module has a corresponding `test_*.py` file
- Tests use pytest and follow AAA (Arrange-Act-Assert) pattern

### Running Focused Tests
When working on a specific module, run only related tests:
```bash
uv run pytest tests/test_client.py -v
```

## Ruff Configuration

The project uses strict linting with `select = ["ALL"]`, then selectively ignores:
- `D*`: Docstring rules (not enforced)
- `T201`: Print statements (allowed for CLI output)
- `FBT001/FBT002`: Boolean trap rules
- `COM812`: Trailing comma enforcement

Test files have relaxed rules (annotations, magic values, asserts, etc.).

## Entry Points

- **CLI entry point**: `mcrcon.cli:main` (defined in `pyproject.toml`)
- **Main flow**: `cli.py` → `client.py` → `repl.py` for interactive mode
- **Non-interactive mode**: Use `-c` flag to run a single command and exit
- **Cache build mode**: Use `--build-cache` to fetch help data, save to cache, and exit (useful for debugging)
- **Debug mode**: Use `--debug` to enable debug logging to stderr (configures `logging.basicConfig` with `DEBUG` level)
- **Color control**: Use `--no-color` to disable ANSI color output
