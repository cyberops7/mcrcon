"""Tests for the help output parser."""

from mcrcon.help_parser import (
    CommandHelp,
    Optional,
    OptionalChoice,
    Required,
    RequiredChoice,
    format_help_response,
    parse_command_help,
    parse_commands,
    parse_help_index,
    parse_page_count,
    parse_player_list,
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
        commands = parse_commands("/advancement (grant|revoke) <targets> <advancement>")

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


class TestParsePageCount:
    def test_extracts_page_count(self):
        text = "--------- Help: Index (1/58) --------------------------\nsome content"
        assert parse_page_count(text) == 58

    def test_different_page_numbers(self):
        text = "--------- Help: Index (3/58) --------------------------"
        assert parse_page_count(text) == 58

    def test_single_page(self):
        text = "--------- Help: Index (1/1) --------------------------"
        assert parse_page_count(text) == 1

    def test_no_page_count(self):
        text = "Some random text without page info"
        assert parse_page_count(text) == 1

    def test_empty_string(self):
        assert parse_page_count("") == 1


class TestParseHelpIndex:
    def test_parses_command_entries(self):
        text = (
            "--------- Help: Index (3/58) --------------------------\n"
            "/.s: Execute last CraftScript\n"
            "//: Toggle the super pickaxe function\n"
            "//calculate: Evaluate a mathematical expression\n"
        )
        commands = parse_help_index(text)

        assert ".s" in commands
        assert "/" in commands
        assert "/calculate" in commands

    def test_skips_header_lines(self):
        text = (
            "--------- Help: Index (1/58) --------------------------\n"
            "/list: Lists players\n"
        )
        commands = parse_help_index(text)
        assert commands == ["list"]

    def test_skips_category_entries(self):
        text = (
            "--------- Help: Index (1/58) --------------------------\n"
            "Aliases: Lists command aliases\n"
            "Minecraft: All commands for Minecraft\n"
            "Essentials: All commands for Essentials\n"
        )
        commands = parse_help_index(text)
        assert commands == []

    def test_skips_meta_lines(self):
        text = (
            "--------- Help: Index (1/58) --------------------------\n"
            "Use /help [n] to get page n of help.\n"
            "/list: Lists players\n"
        )
        commands = parse_help_index(text)
        assert commands == ["list"]

    def test_namespaced_commands(self):
        text = (
            "--------- Help: Index (35/58) -------------------------\n"
            "/minecraft:teammsg: A Mojang provided command.\n"
            "/minecraft:teleport: A Mojang provided command.\n"
        )
        commands = parse_help_index(text)
        assert "minecraft:teammsg" in commands
        assert "minecraft:teleport" in commands

    def test_mixed_commands(self):
        text = (
            "--------- Help: Index (45/58) -------------------------\n"
            "/repair: Repairs the durability of one or all items.\n"
            "/repl: Block replacer tool\n"
            "/minecraft:tell: A Mojang provided command.\n"
        )
        commands = parse_help_index(text)
        assert commands == ["repair", "repl", "minecraft:tell"]

    def test_empty_input(self):
        assert parse_help_index("") == []


class TestParseCommandHelp:
    def test_parses_usage_and_aliases(self):
        text = (
            "--------- Help: /teleport -----------------------------\n"
            "Alias for /tp\n"
            "Description: Teleport to a player.\n"
            "Usage: /tp <player> [otherplayer]\n"
            "Aliases: tele, etele, teleport, eteleport, etp, tp2p, etp2p\n"
        )
        result = parse_command_help(text)

        assert result is not None
        assert len(result.usage_args) == 2
        assert isinstance(result.usage_args[0], Required)
        assert result.usage_args[0].name == "player"
        assert isinstance(result.usage_args[1], Optional)
        assert result.usage_args[1].name == "otherplayer"
        assert "tele" in result.aliases
        assert "etp" in result.aliases
        assert len(result.aliases) == 7

    def test_usage_only(self):
        text = (
            "--------- Help: /ban ---------------------------------\n"
            "Description: Bans a player.\n"
            "Usage: /ban <player> [reason]\n"
        )
        result = parse_command_help(text)

        assert result is not None
        assert len(result.usage_args) == 2
        assert result.aliases == []

    def test_aliases_only(self):
        text = (
            "--------- Help: /tp ----------------------------------\n"
            "Description: Teleport.\n"
            "Aliases: teleport, tele\n"
        )
        result = parse_command_help(text)

        assert result is not None
        assert result.usage_args == []
        assert result.aliases == ["teleport", "tele"]

    def test_no_useful_content(self):
        text = (
            "--------- Help: /minecraft:teleport -------------------\n"
            "Description: A Mojang provided command.\n"
        )
        result = parse_command_help(text)
        assert result is None

    def test_empty_input(self):
        assert parse_command_help("") is None

    def test_usage_with_choices(self):
        text = (
            "--------- Help: /gamemode -----------------------------\n"
            "Description: Sets the game mode.\n"
            "Usage: /gamemode (survival|creative|adventure|spectator) [<target>]\n"
        )
        result = parse_command_help(text)

        assert result is not None
        assert len(result.usage_args) == 2
        assert isinstance(result.usage_args[0], RequiredChoice)
        expected = ["survival", "creative", "adventure", "spectator"]
        assert result.usage_args[0].options == expected
        assert isinstance(result.usage_args[1], Optional)


class TestParsePlayerList:
    def test_single_player(self):
        text = "There are 1 out of maximum 20 players online.\ndefault: Skynet913379\n"
        players = parse_player_list(text)
        assert players == ["Skynet913379"]

    def test_multiple_players_same_group(self):
        text = (
            "There are 3 out of maximum 20 players online.\n"
            "default: Player1, Player2, Player3\n"
        )
        players = parse_player_list(text)
        assert players == ["Player1", "Player2", "Player3"]

    def test_multiple_groups(self):
        text = (
            "There are 4 out of maximum 20 players online.\n"
            "default: Player1, Player2\n"
            "admin: AdminPlayer, ModPlayer\n"
        )
        players = parse_player_list(text)
        assert players == ["Player1", "Player2", "AdminPlayer", "ModPlayer"]

    def test_no_players(self):
        text = "There are 0 out of maximum 20 players online.\n"
        players = parse_player_list(text)
        assert players == []

    def test_empty_input(self):
        assert parse_player_list("") == []
