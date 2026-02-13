"""Strip or convert Minecraft formatting codes from server responses."""

from __future__ import annotations

import re

# Pattern to match Minecraft formatting codes
# Matches: §x§R§R§G§G§B§B (RGB) or §X (single char code)
_MC_FORMAT_PATTERN = re.compile(r"§x(?:§[0-9A-Fa-f]){6}|§.")

_ANSI_RESET = "\033[0m"
_RGB_HEX_DIGITS = 6

# Mapping from Minecraft single-char formatting codes to ANSI escape sequences.
# §k (obfuscated) is intentionally omitted — no terminal equivalent.
_MC_TO_ANSI: dict[str, str] = {
    "0": "\033[30m",  # Black
    "1": "\033[34m",  # Dark Blue
    "2": "\033[32m",  # Dark Green
    "3": "\033[36m",  # Dark Cyan
    "4": "\033[31m",  # Dark Red
    "5": "\033[35m",  # Dark Magenta
    "6": "\033[33m",  # Gold
    "7": "\033[37m",  # Gray
    "8": "\033[90m",  # Dark Gray
    "9": "\033[94m",  # Blue
    "a": "\033[92m",  # Green
    "b": "\033[96m",  # Cyan
    "c": "\033[91m",  # Red
    "d": "\033[95m",  # Magenta
    "e": "\033[93m",  # Yellow
    "f": "\033[97m",  # White
    "l": "\033[1m",  # Bold
    "m": "\033[9m",  # Strikethrough
    "n": "\033[4m",  # Underline
    "o": "\033[3m",  # Italic
    "r": "\033[0m",  # Reset
}


def strip_formatting(text: str) -> str:
    """Remove all Minecraft formatting codes from text.

    Args:
        text: Raw text from the Minecraft server.

    Returns:
        Clean text with all formatting codes removed.
    """
    return _MC_FORMAT_PATTERN.sub("", text)


def convert_formatting(text: str) -> str:
    """Convert Minecraft formatting codes to ANSI escape sequences.

    Translates color codes and text styles (bold, italic, underline, etc.)
    to their ANSI terminal equivalents. RGB colors (§x§R§R§G§G§B§B) are
    converted to 24-bit ANSI color sequences. Codes without a terminal
    equivalent (§k) are stripped.

    A reset sequence is appended at the end if any formatting was applied,
    ensuring the terminal state is left clean.

    Args:
        text: Raw text from the Minecraft server.

    Returns:
        Text with Minecraft codes replaced by ANSI escape sequences.
    """
    has_formatting = False

    def _replace(match: re.Match[str]) -> str:
        nonlocal has_formatting
        code = match.group(0)

        # RGB color: §x§R§R§G§G§B§B
        if code.startswith("§x"):
            hex_chars = [c for c in code if c not in ("§", "x")]
            if len(hex_chars) == _RGB_HEX_DIGITS:
                r = int(hex_chars[0] + hex_chars[1], 16)
                g = int(hex_chars[2] + hex_chars[3], 16)
                b = int(hex_chars[4] + hex_chars[5], 16)
                has_formatting = True
                return f"\033[38;2;{r};{g};{b}m"
            return ""

        # Single-char code: §X
        char = code[1].lower()
        ansi = _MC_TO_ANSI.get(char)
        if ansi is not None:
            has_formatting = True
            return ansi
        return ""

    result = _MC_FORMAT_PATTERN.sub(_replace, text)
    if has_formatting:
        result += _ANSI_RESET
    return result


def format_response(text: str, *, color: bool = True) -> str:
    """Format a server response for terminal display.

    Args:
        text: Raw text from the Minecraft server.
        color: If True, convert formatting codes to ANSI sequences.
            If False, strip all formatting codes.

    Returns:
        Formatted text ready for printing.
    """
    if color:
        return convert_formatting(text)
    return strip_formatting(text)
