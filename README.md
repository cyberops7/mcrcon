# mcrcon

Interactive Minecraft RCON CLI client with dynamic command autocomplete and 1Password integration.

## Features

- **Dynamic autocomplete**: Queries the server's paginated help system to build tab completions for commands, arguments, and player names
- **1Password integration**: Retrieves RCON passwords securely from 1Password CLI
- **Command history**: Persistent history across sessions
- **Auto-reconnection**: Reconnects automatically on connection loss with exponential backoff
- **Multiserver support**: Configure multiple servers with per-server or shared credentials
- **Single-command mode**: Execute one-off commands without entering interactive mode
- **Color output**: Converts Minecraft formatting codes to ANSI terminal colors and styles

## Installation

Requires Python 3.14+ and [uv](https://github.com/astral-sh/uv).

```bash
git clone <repo-url>
cd mcrcon
uv sync
```

## Configuration

Create `~/.config/mcrcon/config.toml`:

```toml
[defaults]
server = "mc-1"

[defaults.credentials]
vault = "Skynet"
item = "minecraft"
field = "RCON_PASSWORD"

[servers.mc-1]
name = "MC-1 (Java + Bedrock)"
host = "10.0.0.112"
port = 25575

[servers.mc-3]
name = "MC-3 (Java + Bedrock)"
host = "10.0.0.114"
port = 25575
```

### Per-Server Credentials

Override credentials for specific servers:

```toml
[servers.production]
name = "Production Server"
host = "prod.example.com"
port = 25575

[servers.production.credentials]
vault = "Production"
item = "minecraft-prod"
field = "RCON_PASSWORD"
```

## Usage

### Interactive Mode

```bash
# Connect to default server
uv run mcrcon

# Connect to specific server from config
uv run mcrcon mc-1

# Connect directly to host:port
uv run mcrcon 10.0.0.112:25575

# Provide password via CLI (bypasses 1Password)
uv run mcrcon mc-1 -p mypassword
```

Once connected, type Minecraft commands:

```
rcon> list
There are 3 of a max of 20 players online: Steve, Alex, Notch
rcon> gamemode creative Steve
Set Steve's game mode to Creative Mode
rcon> exit
```

### Single Command Mode

Execute a command and exit:

```bash
uv run mcrcon mc-1 -c "list"
uv run mcrcon mc-1 -c "time set day"
```

### CLI Reference

```
mcrcon [server] [-p PASSWORD] [-c COMMAND] [--timeout SECONDS] [--no-color] [--raw] [--debug] [--build-cache]
```

| Flag               | Description                                                   |
|--------------------|---------------------------------------------------------------|
| `server`           | Server name (from config) or `host:port`                      |
| `-p`, `--password` | RCON password (overrides 1Password lookup)                    |
| `-c`, `--command`  | Execute a single command and exit                             |
| `--timeout`        | Socket timeout in seconds (default: 10)                       |
| `--no-color`       | Strip formatting codes instead of converting to ANSI colors   |
| `--raw`            | Show raw output with formatting codes visible (for debugging) |
| `--debug`          | Enable debug logging to stderr                                |
| `--build-cache`    | Fetch help data, save to cache, and exit                      |

### Tab Completion

The client dynamically builds completions from the server's available commands. On the first connection, help data is fetched in the background and cached per-server for instant completions on subsequent startups. Player names are also completed and refreshed periodically.

```
rcon> game<TAB>
gamemode  gamerule

rcon> gamemode <TAB>
survival  creative  adventure  spectator

rcon> ban Al<TAB>
Alice
```

### Debugging

Use `--debug` to trace the help fetching pipeline:

```bash
uv run mcrcon mc-1 --debug
```

To build the command cache without entering interactive mode (useful for verifying completions):

```bash
uv run mcrcon mc-1 --build-cache --debug
```

## Local Commands

- `exit` / `quit`: Close the connection and exit
- `reconnect`: Manually trigger reconnection
- `Ctrl+D` or `Ctrl+C`: Exit

## 1Password Setup

Install [1Password CLI](https://developer.1password.com/docs/cli/):

```bash
brew install 1password-cli
```

Create an RCON password item in 1Password:

```bash
op item create \
  --category "API Credential" \
  --title "minecraft" \
  --vault Skynet \
  "password[password]=your-rcon-password" \
  hostname=minecraft.example.com

# Remove default API Credential fields
op item edit minecraft 'valid from[delete]' 'expires[delete]'
```

The field name must match what's configured in `config.toml` (default: `RCON_PASSWORD`).

## Development

### Run Tests

```bash
uv run pytest
```

### Linting

```bash
uv run ruff check src/ tests/
```

### Project Structure

```
src/mcrcon/
├── protocol.py      # RCON wire protocol (packet encode/decode)
├── client.py        # TCP client with auth and multi-packet support
├── config.py        # TOML configuration loading
├── credentials.py   # 1Password CLI integration
├── formatting.py    # Minecraft formatting code conversion/stripping
├── help_parser.py   # Parse server help output into command definitions
├── help_fetcher.py  # Fetch help data from server and manage on-disk cache
├── completer.py     # prompt_toolkit completer from parsed commands
├── repl.py          # Interactive REPL with history and reconnection
└── cli.py           # Entry point and argument parsing
```

## How It Works

1. **Connect & Authenticate**: Establishes TCP connection and authenticates with RCON password
2. **Load Cache**: Loads cached help data from `~/.config/mcrcon/cache/` for instant completions
3. **Background Fetch**: Opens a separate RCON connection to fetch all paginated help pages (`?`, `? 2`, ..., `? N`) and detailed command help (`? <command>`) without blocking the REPL
4. **Strip Formatting**: Removes Minecraft formatting codes (`§x`) from server responses before parsing
5. **Build Completer**: Extracts command names, argument structures (required/optional, choices), aliases, and player names
6. **Interactive Loop**: Provides tab completion, history, and command execution
7. **Periodic Refresh**: The player list is refreshed every 60 seconds in the background

The completer is dynamic, so it automatically supports:
- Modded servers with custom commands
- Plugin commands (EssentialsX, WorldEdit, etc.)
- Different Minecraft versions

## Troubleshooting

### "1Password CLI (op) is not installed"

Install the 1Password CLI:

```bash
brew install 1password-cli
```

### "Authentication failed: incorrect RCON password"

Verify the password in 1Password:

```bash
op item get minecraft --fields label=RCON_PASSWORD --reveal
```

Ensure `enable-rcon=true` and `rcon.password` are set in `server.properties`.

### Connection Timeout

Check that the server is reachable and the RCON port (25575) is open:

```bash
nc -zv 10.0.0.112 25575
```

## License

MIT
