"""Tests for CLI server resolution logic."""

from mcrcon.cli import resolve_server
from mcrcon.config import AppConfig, CredentialConfig, ServerConfig


def _make_config(**overrides) -> AppConfig:
    """Build an AppConfig with sensible defaults."""
    defaults = {
        "default_server": "mc-1",
        "default_credentials": CredentialConfig(
            vault="Skynet", item="minecraft", field="RCON_PASSWORD"
        ),
        "servers": {
            "mc-1": ServerConfig(name="MC-1", host="10.0.0.112"),
            "mc-3": ServerConfig(name="MC-3", host="10.0.0.114"),
        },
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


class TestResolveServer:
    def test_resolve_by_config_name(self):
        config = _make_config()
        name, server = resolve_server("mc-1", config)

        assert name == "mc-1"
        assert server.host == "10.0.0.112"

    def test_resolve_host_port(self):
        config = _make_config()
        name, server = resolve_server("192.168.1.1:25575", config)

        assert server.host == "192.168.1.1"
        assert server.port == 25575

    def test_resolve_bare_hostname(self):
        config = _make_config()
        name, server = resolve_server("myserver.local", config)

        assert server.host == "myserver.local"
        assert server.port == 25575

    def test_resolve_default_server(self):
        config = _make_config()
        name, server = resolve_server(None, config)

        assert name == "mc-1"
        assert server.host == "10.0.0.112"

    def test_resolve_no_default_no_servers(self):
        config = _make_config(default_server=None, servers={})
        # Would normally prompt user, but with no servers it exits.
        # We test that it doesn't crash before prompting.
        # The select_server function handles the sys.exit, so we just test
        # that resolve_server correctly falls through.
        import pytest

        with pytest.raises(SystemExit):
            resolve_server(None, config)

    def test_config_name_takes_precedence_over_host_parse(self):
        # If a server name contains a colon (unlikely but possible)
        config = _make_config()
        name, server = resolve_server("mc-1", config)

        # Should resolve as config name, not try to parse as host:port
        assert server.host == "10.0.0.112"

    def test_resolve_host_with_invalid_port(self):
        config = _make_config()
        name, server = resolve_server("myhost:notaport", config)

        # Falls through to bare hostname treatment
        assert server.host == "myhost:notaport"
        assert server.port == 25575
