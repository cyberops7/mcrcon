"""Tests for the help output parser."""

from mcrcon.help_parser import (
    Optional,
    OptionalChoice,
    Required,
    RequiredChoice,
    format_help_response,
    parse_commands,
)


class TestFormatHelpResponse:
    def test_splits_concatenated_commands(self):
        raw = "/ban <targets> [<reason>]/banlist (ips|players)"
        result = format_help_response(raw)

        assert "/ban" in result
        assert "/banlist" in result
        lines = result.strip().splitlines()
        assert len(lines) == 2

    def test_preserves_already_formatted(self):
        raw = "/ban <targets> [<reason>]\n/banlist (ips|players)"
        result = format_help_response(raw)

        lines = result.strip().splitlines()
        assert len(lines) == 2

    def test_strips_whitespace(self):
        raw = "  /list  "
        result = format_help_response(raw)
        assert result == "/list"


class TestParseCommands:
    def test_simple_command(self):
        commands = parse_commands("/list\n/seed")

        assert "list" in commands
        assert "seed" in commands
        assert commands["list"] == []
        assert commands["seed"] == []

    def test_required_args(self):
        commands = parse_commands("/ban <targets>")

        assert "ban" in commands
        args = commands["ban"]
        assert len(args) == 1
        assert isinstance(args[0], Required)
        assert args[0].name == "targets"

    def test_optional_args(self):
        commands = parse_commands("/ban <targets> [<reason>]")

        args = commands["ban"]
        required = [a for a in args if isinstance(a, Required)]
        optional = [a for a in args if isinstance(a, Optional)]

        assert len(required) == 1
        assert required[0].name == "targets"
        assert len(optional) == 1
        assert optional[0].name == "reason"

    def test_required_choice(self):
        commands = parse_commands("/difficulty (peaceful|easy|normal|hard)")

        args = commands["difficulty"]
        assert len(args) == 1
        assert isinstance(args[0], RequiredChoice)
        assert args[0].options == ["peaceful", "easy", "normal", "hard"]

    def test_optional_choice(self):
        commands = parse_commands("/banlist [ips|players]")

        args = commands["banlist"]
        assert len(args) == 1
        assert isinstance(args[0], OptionalChoice)
        assert args[0].options == ["ips", "players"]

    def test_alias(self):
        commands = parse_commands("/tell <targets> <message>\n/msg -> tell")

        assert "msg" in commands
        assert "tell" in commands
        # Alias should have the same args as target
        assert len(commands["msg"]) == len(commands["tell"])

    def test_command_without_slash(self):
        commands = parse_commands("list\nseed")

        assert "list" in commands
        assert "seed" in commands

    def test_mixed_args(self):
        commands = parse_commands(
            "/advancement (grant|revoke) <targets> <advancement>"
        )

        args = commands["advancement"]
        choices = [a for a in args if isinstance(a, RequiredChoice)]
        required = [a for a in args if isinstance(a, Required)]

        assert len(choices) == 1
        assert choices[0].options == ["grant", "revoke"]
        assert len(required) == 2

    def test_empty_input(self):
        commands = parse_commands("")
        assert commands == {}

    def test_realistic_help_output(self):
        help_text = (
            "/advancement (grant|revoke) <targets> <advancement>\n"
            "/ban <targets> [<reason>]\n"
            "/ban-ip <target> [<reason>]\n"
            "/banlist [ips|players]\n"
            "/clear <targets> [<item>] [<maxCount>]\n"
            "/defaultgamemode (survival|creative|adventure|spectator)\n"
            "/difficulty (peaceful|easy|normal|hard)\n"
            "/gamemode (survival|creative|adventure|spectator) [<target>]\n"
            "/help [<command>]\n"
            "/kick <targets> [<reason>]\n"
            "/list\n"
            "/msg -> tell\n"
            "/say <message>\n"
            "/seed\n"
            "/stop\n"
            "/tell <targets> <message>\n"
            "/time (add|query|set) <value>\n"
            "/weather (clear|rain|thunder) [<duration>]\n"
            "/whitelist (add|list|off|on|reload|remove) [<targets>]\n"
        )

        commands = parse_commands(help_text)

        assert len(commands) >= 18
        assert "advancement" in commands
        assert "msg" in commands
        assert "list" in commands

        # Verify specific argument structures
        difficulty = commands["difficulty"]
        assert len(difficulty) == 1
        assert isinstance(difficulty[0], RequiredChoice)
        assert "hard" in difficulty[0].options
