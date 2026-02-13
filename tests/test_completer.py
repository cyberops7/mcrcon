"""Tests for the Minecraft command completer."""

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from mcrcon.completer import MinecraftCompleter
from mcrcon.help_parser import Optional, Required, RequiredChoice


def _completions(completer, text):
    """Helper to get completion text values for a given input."""
    doc = Document(text, len(text))
    event = CompleteEvent()
    return [c.text for c in completer.get_completions(doc, event)]


class TestCommandCompletion:
    def test_completes_command_names(self):
        completer = MinecraftCompleter({"ban": [], "banlist": [], "seed": []})
        results = _completions(completer, "ba")

        assert "ban" in results
        assert "banlist" in results
        assert "seed" not in results

    def test_includes_local_commands(self):
        completer = MinecraftCompleter({})
        results = _completions(completer, "ex")
        assert "exit" in results

    def test_empty_prefix_shows_all(self):
        completer = MinecraftCompleter({"ban": [], "list": []})
        results = _completions(completer, "")

        assert "ban" in results
        assert "list" in results
        assert "exit" in results
        assert "quit" in results


class TestArgumentCompletion:
    def test_completes_required_choice(self):
        completer = MinecraftCompleter(
            {
                "difficulty": [
                    RequiredChoice(options=["peaceful", "easy", "normal", "hard"]),
                ],
            }
        )
        results = _completions(completer, "difficulty ")
        assert "peaceful" in results
        assert "hard" in results

    def test_completes_with_prefix(self):
        completer = MinecraftCompleter(
            {
                "difficulty": [
                    RequiredChoice(options=["peaceful", "easy", "normal", "hard"]),
                ],
            }
        )
        results = _completions(completer, "difficulty p")
        assert results == ["peaceful"]


class TestPlayerCompletion:
    def test_completes_player_arg_names(self):
        completer = MinecraftCompleter(
            {
                "ban": [Required(name="player")],
            }
        )
        completer.update_players(["Alice", "Bob", "Charlie"])

        results = _completions(completer, "ban ")
        assert "Alice" in results
        assert "Bob" in results

    def test_player_prefix_filtering(self):
        completer = MinecraftCompleter(
            {
                "ban": [Required(name="player")],
            }
        )
        completer.update_players(["Alice", "Bob", "Charlie"])

        results = _completions(completer, "ban A")
        assert results == ["Alice"]

    def test_player_completion_for_target_arg(self):
        completer = MinecraftCompleter(
            {
                "kick": [Required(name="targets")],
            }
        )
        completer.update_players(["Alice"])

        results = _completions(completer, "kick ")
        assert "Alice" in results

    def test_no_player_completion_for_non_player_arg(self):
        completer = MinecraftCompleter(
            {
                "say": [Required(name="message")],
            }
        )
        completer.update_players(["Alice"])

        results = _completions(completer, "say ")
        assert results == []

    def test_fallback_player_completion_when_no_args(self):
        completer = MinecraftCompleter({"ban": []})
        completer.update_players(["Alice", "Bob"])

        results = _completions(completer, "ban ")
        assert "Alice" in results
        assert "Bob" in results

    def test_optional_player_arg(self):
        completer = MinecraftCompleter(
            {
                "tp": [Required(name="player"), Optional(name="target")],
            }
        )
        completer.update_players(["Alice", "Bob"])

        # Second argument is also a player-type arg
        results = _completions(completer, "tp Alice ")
        assert "Alice" in results
        assert "Bob" in results


class TestDynamicUpdates:
    def test_update_commands(self):
        completer = MinecraftCompleter({})
        assert _completions(completer, "ba") == []

        completer.update_commands({"ban": [], "banlist": []})
        results = _completions(completer, "ba")
        assert "ban" in results
        assert "banlist" in results

    def test_update_players(self):
        completer = MinecraftCompleter({"kick": [Required(name="player")]})
        assert _completions(completer, "kick ") == []

        completer.update_players(["Alice"])
        results = _completions(completer, "kick ")
        assert "Alice" in results
