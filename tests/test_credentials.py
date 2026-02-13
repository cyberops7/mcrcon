"""Tests for 1Password credential retrieval."""

from unittest.mock import patch

import pytest

from mcrcon.config import CredentialConfig
from mcrcon.credentials import CredentialError, get_rcon_password

CREDS = CredentialConfig(vault="Skynet", item="minecraft", field="RCON_PASSWORD")


class TestGetRconPassword:
    @patch("mcrcon.credentials.shutil.which", return_value="/usr/local/bin/op")
    @patch("mcrcon.credentials.subprocess.run")
    def test_success(self, mock_run, _mock_which):
        mock_run.return_value.stdout = "my-secret-password\n"
        mock_run.return_value.returncode = 0

        result = get_rcon_password(CREDS)

        assert result == "my-secret-password"
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "/usr/local/bin/op"
        assert "minecraft" in cmd
        assert "--vault" in cmd
        assert "Skynet" in cmd

    @patch("mcrcon.credentials.shutil.which", return_value=None)
    def test_op_not_found(self, _mock_which):
        with pytest.raises(CredentialError, match="not installed"):
            get_rcon_password(CREDS)

    @patch("mcrcon.credentials.shutil.which", return_value="/usr/local/bin/op")
    @patch("mcrcon.credentials.subprocess.run")
    def test_op_failure(self, mock_run, _mock_which):
        import subprocess

        mock_run.side_effect = subprocess.CalledProcessError(
            1, "op", stderr="item not found"
        )

        with pytest.raises(CredentialError, match="Failed to retrieve"):
            get_rcon_password(CREDS)

    @patch("mcrcon.credentials.shutil.which", return_value="/usr/local/bin/op")
    @patch("mcrcon.credentials.subprocess.run")
    def test_op_timeout(self, mock_run, _mock_which):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("op", 30)

        with pytest.raises(CredentialError, match="timed out"):
            get_rcon_password(CREDS)

    @patch("mcrcon.credentials.shutil.which", return_value="/usr/local/bin/op")
    @patch("mcrcon.credentials.subprocess.run")
    def test_empty_password(self, mock_run, _mock_which):
        mock_run.return_value.stdout = "\n"
        mock_run.return_value.returncode = 0

        with pytest.raises(CredentialError, match="Empty password"):
            get_rcon_password(CREDS)

    def test_custom_credentials(self):
        custom = CredentialConfig(vault="Personal", item="other-mc", field="pass")
        with (
            patch("mcrcon.credentials.shutil.which", return_value="/usr/local/bin/op"),
            patch("mcrcon.credentials.subprocess.run") as mock_run,
        ):
            mock_run.return_value.stdout = "custom-pass\n"
            mock_run.return_value.returncode = 0

            result = get_rcon_password(custom)

            assert result == "custom-pass"
            cmd = mock_run.call_args[0][0]
            assert "other-mc" in cmd
            assert "Personal" in cmd
