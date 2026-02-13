"""Tests for Minecraft formatting code handling."""

from mcrcon.formatting import convert_formatting, format_response, strip_formatting

# --- Tests for strip_formatting ---


def test_strip_rgb_color():
    """Strip RGB color codes (§x§R§R§G§G§B§B)."""
    text = "§x§4§4§8§8§F§F§lBlueMap §fStatus"
    result = strip_formatting(text)
    assert result == "BlueMap Status"


def test_strip_legacy_colors():
    """Strip legacy color codes (§0-9, §a-f)."""
    text = "§f6§x§8§8§F§F§8§8 render-threads are §fidle§f"
    result = strip_formatting(text)
    assert result == "6 render-threads are idle"


def test_strip_formatting_codes():
    """Strip formatting codes like §l (bold), §r (reset)."""
    text = "§lBold§r Normal"
    result = strip_formatting(text)
    assert result == "Bold Normal"


def test_strip_mixed_formatting():
    """Strip a mix of RGB, legacy colors, and formatting codes."""
    text = "§x§8§8§F§F§8§8✔ §f3§x§8§8§F§F§8§8 maps are updated§f"
    result = strip_formatting(text)
    assert result == "✔ 3 maps are updated"


def test_strip_multiple_codes_in_sequence():
    """Strip multiple formatting codes appearing back-to-back."""
    text = "§7└ last active §f5 minutes§7 ago§f"
    result = strip_formatting(text)
    assert result == "└ last active 5 minutes ago"


def test_strip_empty_string():
    """Handle empty string input."""
    assert strip_formatting("") == ""


def test_strip_no_formatting_codes():
    """Text without formatting codes remains unchanged."""
    text = "Plain text without codes"
    result = strip_formatting(text)
    assert result == text


def test_strip_uppercase_hex_in_rgb():
    """RGB codes can use uppercase hex digits."""
    text = "§x§F§F§0§0§0§0Red Text"
    result = strip_formatting(text)
    assert result == "Red Text"


def test_strip_lowercase_hex_in_rgb():
    """RGB codes can use lowercase hex digits."""
    text = "§x§f§f§0§0§0§0Red Text"
    result = strip_formatting(text)
    assert result == "Red Text"


# --- Tests for convert_formatting ---


def test_convert_legacy_color():
    """Convert a legacy color code to the corresponding ANSI sequence."""
    result = convert_formatting("§aGreen Text")
    assert result == "\033[0m\033[92mGreen Text\033[0m"


def test_convert_bold():
    """Convert §l to ANSI bold."""
    result = convert_formatting("§lBold")
    assert result == "\033[1mBold\033[0m"


def test_convert_italic():
    """Convert §o to ANSI italic."""
    result = convert_formatting("§oItalic")
    assert result == "\033[3mItalic\033[0m"


def test_convert_underline():
    """Convert §n to ANSI underline."""
    result = convert_formatting("§nUnderline")
    assert result == "\033[4mUnderline\033[0m"


def test_convert_strikethrough():
    """Convert §m to ANSI strikethrough."""
    result = convert_formatting("§mStrike")
    assert result == "\033[9mStrike\033[0m"


def test_convert_reset_in_middle():
    """§r in the middle of text resets formatting."""
    result = convert_formatting("§lBold§r Normal")
    assert result == "\033[1mBold\033[0m Normal\033[0m"


def test_convert_rgb_color():
    """Convert RGB color codes to 24-bit ANSI sequences."""
    result = convert_formatting("§x§F§F§0§0§0§0Red")
    assert result == "\033[0m\033[38;2;255;0;0mRed\033[0m"


def test_convert_rgb_lowercase():
    """RGB codes work with lowercase hex digits."""
    result = convert_formatting("§x§4§4§8§8§f§fBlue")
    assert result == "\033[0m\033[38;2;68;136;255mBlue\033[0m"


def test_convert_mixed_rgb_and_legacy():
    """Mixed RGB and legacy codes are both converted."""
    result = convert_formatting("§x§4§4§8§8§F§F§lBlueMap §fStatus")
    assert (
        result
        == "\033[0m\033[38;2;68;136;255m\033[1mBlueMap \033[0m\033[97mStatus\033[0m"
    )


def test_convert_obfuscated_stripped():
    """§k (obfuscated) has no ANSI equivalent and is stripped."""
    result = convert_formatting("§kHidden")
    assert result == "Hidden"


def test_convert_obfuscated_no_trailing_reset():
    """Stripping §k alone does not add a trailing reset."""
    result = convert_formatting("§kHidden")
    assert not result.endswith("\033[0m")


def test_convert_no_formatting():
    """Text without formatting codes is returned unchanged."""
    result = convert_formatting("Plain text")
    assert result == "Plain text"


def test_convert_empty_string():
    """Empty input returns empty output."""
    assert convert_formatting("") == ""


def test_convert_preserves_unicode():
    """Unicode characters like checkmarks and box-drawing are preserved."""
    result = convert_formatting("§x§8§8§F§F§8§8✔ Done")
    assert "✔ Done" in result


def test_convert_case_insensitive_codes():
    """Legacy color codes are case-insensitive (§A == §a)."""
    upper = convert_formatting("§AText")
    lower = convert_formatting("§aText")
    assert upper == lower


def test_convert_multiple_colors():
    """Multiple color switches in a single string."""
    result = convert_formatting("§cRed §aGreen §9Blue")
    assert (
        result == "\033[0m\033[91mRed \033[0m\033[92mGreen \033[0m\033[94mBlue\033[0m"
    )


def test_convert_all_legacy_colors():
    """Each legacy color code maps to the correct ANSI sequence."""
    expected = {
        "0": "\033[30m",
        "1": "\033[34m",
        "2": "\033[32m",
        "3": "\033[36m",
        "4": "\033[31m",
        "5": "\033[35m",
        "6": "\033[33m",
        "7": "\033[37m",
        "8": "\033[90m",
        "9": "\033[94m",
        "a": "\033[92m",
        "b": "\033[96m",
        "c": "\033[91m",
        "d": "\033[95m",
        "e": "\033[93m",
        "f": "\033[97m",
    }
    for code, ansi in expected.items():
        result = convert_formatting(f"§{code}X")
        assert result == f"\033[0m{ansi}X\033[0m", f"Failed for §{code}"


def test_convert_color_resets_strikethrough():
    """Color codes reset formatting like strikethrough (Minecraft behavior)."""
    # Simulates: cyan strikethrough "====", then green "Server Uptime:"
    # (no strikethrough on the second line)
    result = convert_formatting("§b§m====\n§aServer Uptime:")
    # After §b§m, strikethrough is active
    # When §a appears, it should reset (clear strikethrough) then apply green
    assert result == "\033[0m\033[96m\033[9m====\n\033[0m\033[92mServer Uptime:\033[0m"


# --- Tests for format_response ---


def test_format_response_color_true():
    """format_response with color=True converts codes to ANSI."""
    result = format_response("§aGreen", color=True)
    assert "\033[92m" in result


def test_format_response_color_false():
    """format_response with color=False strips all codes."""
    result = format_response("§aGreen", color=False)
    assert result == "Green"


def test_format_response_default_is_color():
    """format_response defaults to color=True."""
    result = format_response("§aGreen")
    assert "\033[92m" in result
