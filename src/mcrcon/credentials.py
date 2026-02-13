"""Retrieve RCON credentials from 1Password using the op CLI."""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcrcon.config import CredentialConfig


class CredentialError(Exception):
    """Raised when credentials cannot be retrieved from 1Password."""


def get_rcon_password(creds: CredentialConfig) -> str:
    """Retrieve the RCON password from 1Password.

    Args:
        creds: The credential configuration specifying vault, item, and field.

    Returns:
        The password string.

    Raises:
        CredentialError: If the op CLI is not found or the retrieval fails.
    """
    if not shutil.which("op"):
        msg = "1Password CLI (op) is not installed or not in PATH"
        raise CredentialError(msg)

    op_path = shutil.which("op")
    try:
        result = subprocess.run(  # noqa: S603
            [
                op_path,
                "item",
                "get",
                creds.item,
                "--vault",
                creds.vault,
                "--fields",
                f"label={creds.field}",
                "--reveal",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as e:
        msg = f"Failed to retrieve password from 1Password: {e.stderr.strip()}"
        raise CredentialError(msg) from e
    except subprocess.TimeoutExpired as e:
        msg = "1Password CLI timed out -- is the session active?"
        raise CredentialError(msg) from e

    password = result.stdout.strip()
    if not password:
        msg = (
            "Empty password retrieved from 1Password"
            f" (vault={creds.vault}, item={creds.item})"
        )
        raise CredentialError(msg)

    return password
