"""Tests for configuration loading."""

from pathlib import Path
from textwrap import dedent

from mcrcon.config import AppConfig, CredentialConfig, ServerConfig, load_config


class TestLoadConfig:
    def test_default_config_when_no_file(self, tmp_path: Path):
        config = load_config(tmp_path / "nonexistent.toml")

        assert config.default_server == "mc-1"
        assert "mc-1" in config.servers
        assert "mc-3" in config.servers
        assert config.default_credentials is not None
        assert config.default_credentials.vault == "Skynet"

    def test_load_full_config(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            dedent("""\
            [defaults]
            server = "test-server"

            [defaults.credentials]
            vault = "TestVault"
            item = "test-item"
            field = "TEST_PASS"

            [servers.test-server]
            name = "Test Server"
            host = "192.168.1.1"
            port = 25575
        """)
        )

        config = load_config(config_file)

        assert config.default_server == "test-server"
        assert config.default_credentials.vault == "TestVault"
        assert config.default_credentials.item == "test-item"
        assert config.default_credentials.field == "TEST_PASS"
        assert config.servers["test-server"].host == "192.168.1.1"
        assert config.servers["test-server"].name == "Test Server"

    def test_per_server_credentials(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            dedent("""\
            [defaults.credentials]
            vault = "Default"
            item = "default-item"
            field = "DEFAULT_PASS"

            [servers.srv1]
            name = "Server 1"
            host = "10.0.0.1"

            [servers.srv2]
            name = "Server 2"
            host = "10.0.0.2"

            [servers.srv2.credentials]
            vault = "Custom"
            item = "custom-item"
            field = "CUSTOM_PASS"
        """)
        )

        config = load_config(config_file)

        # srv1 has no per-server credentials
        assert config.servers["srv1"].credentials is None

        # srv2 has per-server credentials
        assert config.servers["srv2"].credentials is not None
        assert config.servers["srv2"].credentials.vault == "Custom"

    def test_default_port(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            dedent("""\
            [servers.s1]
            host = "10.0.0.1"
        """)
        )

        config = load_config(config_file)
        assert config.servers["s1"].port == 25575

    def test_name_defaults_to_key(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            dedent("""\
            [servers.myserver]
            host = "10.0.0.1"
        """)
        )

        config = load_config(config_file)
        assert config.servers["myserver"].name == "myserver"

    def test_empty_config(self, tmp_path: Path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("")

        config = load_config(config_file)
        assert config.default_server is None
        assert config.default_credentials is None
        assert config.servers == {}


class TestCredentialResolution:
    def test_per_server_takes_precedence(self):
        per_server = CredentialConfig(vault="A", item="a", field="FA")
        default = CredentialConfig(vault="B", item="b", field="FB")

        server = ServerConfig(name="s", host="h", credentials=per_server)
        result = server.resolve_credentials(default)

        assert result is per_server

    def test_falls_back_to_default(self):
        default = CredentialConfig(vault="B", item="b", field="FB")
        server = ServerConfig(name="s", host="h")
        result = server.resolve_credentials(default)

        assert result is default

    def test_no_credentials_available(self):
        server = ServerConfig(name="s", host="h")
        result = server.resolve_credentials(None)

        assert result is None
