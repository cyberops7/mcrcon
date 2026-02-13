"""CLI entry point for the RCON client."""

from __future__ import annotations

import argparse
import sys

from mcrcon.client import (
    AuthenticationError,
    RconClient,
)
from mcrcon.client import (
    ConnectionError as RconConnectionError,
)
from mcrcon.config import (
    AppConfig,
    ServerConfig,
    ensure_config_dir,
    load_config,
)
from mcrcon.credentials import CredentialError, get_rcon_password
from mcrcon.formatting import format_response
from mcrcon.repl import run_repl


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="mcrcon",
        description="Interactive Minecraft RCON client",
    )
    parser.add_argument(
        "server",
        nargs="?",
        help="Server name (from config) or host:port (e.g., 10.0.0.112:25575)",
    )
    parser.add_argument(
        "-p",
        "--password",
        help="RCON password (overrides 1Password lookup)",
    )
    parser.add_argument(
        "-c",
        "--command",
        help="Execute a single command and exit (non-interactive mode)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Socket timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="Strip formatting codes instead of converting to ANSI colors",
    )
    return parser


def select_server(config: AppConfig) -> tuple[str, ServerConfig]:
    """Prompt the user to select from configured servers.

    Returns (key, ServerConfig).
    """
    servers = list(config.servers.items())
    if not servers:
        print("No servers configured.", file=sys.stderr)
        sys.exit(1)

    print("Available servers:")
    for i, (_key, srv) in enumerate(servers, 1):
        print(f"  {i}. {srv.name} ({srv.host}:{srv.port})")

    while True:
        try:
            choice = input(f"\nSelect server [1-{len(servers)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(servers):
                return servers[idx]
        except (ValueError, EOFError):
            pass
        print(f"Please enter a number between 1 and {len(servers)}")


def resolve_server(
    server_arg: str | None, config: AppConfig
) -> tuple[str, ServerConfig]:
    """Resolve the target server from CLI arg or interactive selection.

    Returns (display_name, ServerConfig).
    """
    if server_arg is not None:
        # Check if it's a configured server name
        if server_arg in config.servers:
            return server_arg, config.servers[server_arg]

        # Try parsing as host:port
        if ":" in server_arg:
            host, port_str = server_arg.rsplit(":", 1)
            try:
                port = int(port_str)
                return server_arg, ServerConfig(name=server_arg, host=host, port=port)
            except ValueError:
                pass

        # Treat as hostname with default port
        return server_arg, ServerConfig(name=server_arg, host=server_arg)

    # No server arg provided -- check for default
    if config.default_server and config.default_server in config.servers:
        key = config.default_server
        return key, config.servers[key]

    # Prompt user to select
    return select_server(config)


def resolve_password(
    password_arg: str | None,
    server: ServerConfig,
    config: AppConfig,
) -> str:
    """Resolve the RCON password from CLI flag, per-server, or default credentials."""
    if password_arg is not None:
        return password_arg

    creds = server.resolve_credentials(config.default_credentials)
    if creds is None:
        print(
            "Error: no credentials configured for this server and no defaults set.\n"
            "Use -p to provide a password, or configure credentials in "
            "~/.config/mcrcon/config.toml",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        return get_rcon_password(creds)
    except CredentialError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args()

    ensure_config_dir()
    config = load_config()

    display_name, server = resolve_server(args.server, config)
    password = resolve_password(args.password, server, config)

    # Connect and authenticate
    client = RconClient(server.host, server.port, timeout=args.timeout)
    try:
        client.connect()
        client.authenticate(password)
    except RconConnectionError as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        sys.exit(1)
    except AuthenticationError as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        client.close()
        sys.exit(1)

    # Non-interactive mode: run single command and exit
    if args.command:
        try:
            response = client.command(args.command)
            if response:
                print(format_response(response, color=not args.no_color))
        finally:
            client.close()
        return

    # Interactive mode
    print(f"Connected to {display_name} ({server.host}:{server.port})")
    print("Type 'help' for server commands, Ctrl+D or 'exit' to quit.\n")
    try:
        run_repl(client, password, color=not args.no_color)
    finally:
        client.close()
