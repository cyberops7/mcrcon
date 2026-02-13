"""Tests for the RCON client."""

import struct
from unittest.mock import MagicMock, patch

import pytest

from mcrcon.client import AuthenticationError, ConnectionError, RconClient
from mcrcon.protocol import Packet, PacketType


def _make_response_bytes(request_id: int, payload: str) -> bytes:
    """Build raw bytes for a complete RCON response packet (with length prefix)."""
    packet = Packet(
        request_id=request_id,
        packet_type=PacketType.RESPONSE,
        payload=payload,
    )
    return packet.encode()


def _mock_socket_with_responses(*response_packets: bytes):
    """Create a mock socket that returns the given response packets in sequence."""
    all_data = b"".join(response_packets)
    offset = 0

    def mock_recv(num_bytes):
        nonlocal offset
        if offset >= len(all_data):
            return b""
        chunk = all_data[offset : offset + num_bytes]
        offset += len(chunk)
        return chunk

    mock_sock = MagicMock()
    mock_sock.recv.side_effect = mock_recv
    return mock_sock


class TestConnect:
    def test_connect_success(self):
        with patch("mcrcon.client.socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock

            client = RconClient("localhost", 25575)
            client.connect()

            assert client.connected
            mock_sock.connect.assert_called_once_with(("localhost", 25575))
            mock_sock.settimeout.assert_called_once_with(10.0)

    def test_connect_failure(self):
        with patch("mcrcon.client.socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = OSError("Connection refused")
            mock_socket_cls.return_value = mock_sock

            client = RconClient("localhost", 25575)
            with pytest.raises(ConnectionError, match="Connection refused"):
                client.connect()

    def test_close(self):
        with patch("mcrcon.client.socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock

            client = RconClient("localhost", 25575)
            client.connect()
            client.close()

            assert not client.connected
            mock_sock.close.assert_called_once()


class TestAuthenticate:
    def test_auth_success(self):
        # Auth success: server echoes back the same request_id with type 2
        response = Packet(request_id=1, packet_type=PacketType.COMMAND, payload="")
        mock_sock = _mock_socket_with_responses(response.encode())

        client = RconClient("localhost", 25575)
        client._sock = mock_sock
        client.authenticate("password")
        # Should not raise

    def test_auth_failure(self):
        # Auth failure: server returns request_id == -1
        response = Packet(request_id=-1, packet_type=PacketType.COMMAND, payload="")
        mock_sock = _mock_socket_with_responses(response.encode())

        client = RconClient("localhost", 25575)
        client._sock = mock_sock

        with pytest.raises(AuthenticationError, match="incorrect RCON password"):
            client.authenticate("wrong_password")


class TestCommand:
    def test_single_packet_response(self):
        import mcrcon.client

        req_id = 100
        response = _make_response_bytes(req_id, "There are 0 players online")
        sentinel = _make_response_bytes(9999, "")
        mock_sock = _mock_socket_with_responses(response, sentinel)

        client = RconClient("localhost", 25575)
        client._sock = mock_sock

        original_counter = mcrcon.client._request_id_counter
        mcrcon.client._request_id_counter = iter([req_id])
        try:
            result = client.command("list")
        finally:
            mcrcon.client._request_id_counter = original_counter

        assert "players online" in result

    def test_multi_packet_response(self):
        import mcrcon.client

        req_id = 200
        part1 = _make_response_bytes(req_id, "First part ")
        part2 = _make_response_bytes(req_id, "Second part")
        sentinel = _make_response_bytes(9999, "")
        mock_sock = _mock_socket_with_responses(part1, part2, sentinel)

        client = RconClient("localhost", 25575)
        client._sock = mock_sock

        original_counter = mcrcon.client._request_id_counter
        mcrcon.client._request_id_counter = iter([req_id])
        try:
            result = client.command("help")
        finally:
            mcrcon.client._request_id_counter = original_counter

        assert result == "First part Second part"

    def test_not_connected(self):
        client = RconClient("localhost", 25575)
        with pytest.raises(ConnectionError, match="Not connected"):
            client.command("list")

    def test_connection_closed_by_server(self):
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b""  # EOF

        client = RconClient("localhost", 25575)
        client._sock = mock_sock

        with pytest.raises(ConnectionError, match="Connection closed by server"):
            client.command("list")
