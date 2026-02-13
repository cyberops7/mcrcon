"""Tests for the help fetcher and cache system."""

from unittest.mock import MagicMock

from mcrcon.help_fetcher import (
    _deserialize_commands,
    _serialize_commands,
    fetch_all_help,
    fetch_player_list,
    load_cache,
    save_cache,
)
from mcrcon.help_parser import Optional, Required, RequiredChoice


class TestCacheRoundtrip:
    def test_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mcrcon.help_fetcher.CACHE_DIR", tmp_path)

        commands = {
            "ban": [Required(name="player"), Optional(name="reason")],
            "difficulty": [RequiredChoice(options=["easy", "hard"])],
            "list": [],
        }

        save_cache("localhost", 25575, commands)
        loaded = load_cache("localhost", 25575)

        assert loaded is not None
        assert loaded == commands

    def test_load_missing_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mcrcon.help_fetcher.CACHE_DIR", tmp_path)
        assert load_cache("nonexistent", 25575) is None

    def test_load_corrupt_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mcrcon.help_fetcher.CACHE_DIR", tmp_path)
        cache_file = tmp_path / "localhost_25575.json"
        cache_file.write_text("not valid json{{{")
        assert load_cache("localhost", 25575) is None

    def test_load_wrong_version(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mcrcon.help_fetcher.CACHE_DIR", tmp_path)
        cache_file = tmp_path / "localhost_25575.json"
        cache_file.write_text('{"version": 999, "commands": {}}')
        assert load_cache("localhost", 25575) is None


class TestSerializeDeserialize:
    def test_roundtrip_all_arg_types(self):
        from mcrcon.help_parser import OptionalChoice

        commands = {
            "test": [
                Required(name="target"),
                Optional(name="reason"),
                RequiredChoice(options=["a", "b"]),
                OptionalChoice(options=["x", "y"]),
            ],
        }

        serialized = _serialize_commands(commands)
        deserialized = _deserialize_commands(serialized)
        assert deserialized == commands

    def test_empty_commands(self):
        assert _deserialize_commands(_serialize_commands({})) == {}


class TestFetchAllHelp:
    def test_fetches_all_pages_and_details(self):
        client = MagicMock()

        # Set up page responses
        responses = {
            "?": (
                "--------- Help: Index (1/2) --------------------------\n"
                "Minecraft: All commands for Minecraft\n"
                "/ban: Bans a player\n"
            ),
            "? 2": (
                "--------- Help: Index (2/2) --------------------------\n"
                "/list: Lists players\n"
            ),
            "? ban": (
                "--------- Help: /ban ---------------------------------\n"
                "Description: Bans a player.\n"
                "Usage: /ban <player> [reason]\n"
            ),
            "? list": (
                "--------- Help: /list --------------------------------\n"
                "Description: Lists players.\n"
            ),
        }
        client.command.side_effect = lambda cmd: responses.get(cmd, "")

        commands = fetch_all_help(client)

        assert "ban" in commands
        assert "list" in commands
        # Ban should have parsed args from detailed help
        assert len(commands["ban"]) == 2

    def test_handles_namespaced_commands(self):
        client = MagicMock()

        responses = {
            "?": (
                "--------- Help: Index (1/1) --------------------------\n"
                "/minecraft:teleport: A Mojang provided command.\n"
                "/teleport: Teleport to a player.\n"
            ),
            # Only the bare name should be queried
            "? teleport": (
                "--------- Help: /teleport -----------------------------\n"
                "Description: Teleport to a player.\n"
                "Usage: /tp <player> [otherplayer]\n"
                "Aliases: tele, etp\n"
            ),
        }
        client.command.side_effect = lambda cmd: responses.get(cmd, "")

        commands = fetch_all_help(client)

        assert "teleport" in commands
        assert "minecraft:teleport" in commands
        # Aliases should be registered too
        assert "tele" in commands
        assert "etp" in commands
        # All should share the same args
        assert commands["teleport"] == commands["minecraft:teleport"]
        assert commands["teleport"] == commands["tele"]


class TestFetchPlayerList:
    def test_fetches_and_parses(self):
        client = MagicMock()
        client.command.return_value = (
            "There are 2 out of maximum 20 players online.\ndefault: Alice, Bob\n"
        )

        players = fetch_player_list(client)
        client.command.assert_called_once_with("online")
        assert players == ["Alice", "Bob"]
