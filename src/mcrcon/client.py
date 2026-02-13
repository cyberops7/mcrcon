"""High-level RCON client with connection management."""

from __future__ import annotations

import contextlib
import itertools
import socket
import struct

from mcrcon.protocol import Packet, PacketType

_SENTINEL_ID = 9999
_request_id_counter = itertools.count(1)


class RconError(Exception):
    """Base exception for RCON errors."""


class AuthenticationError(RconError):
    """Raised when RCON authentication fails."""


class ConnectionError(RconError):  # noqa: A001
    """Raised when the connection to the server is lost or cannot be established."""


class RconClient:
    """Manages a TCP connection to a Minecraft RCON server."""

    def __init__(self, host: str, port: int, timeout: float = 10.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None

    @property
    def connected(self) -> bool:
        """Whether the client has an active socket connection."""
        return self._sock is not None

    def connect(self) -> None:
        """Establish a TCP connection to the RCON server."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            self._sock = sock
        except OSError as e:
            msg = f"Failed to connect to {self.host}:{self.port}: {e}"
            raise ConnectionError(msg) from e

    def close(self) -> None:
        """Close the TCP connection."""
        if self._sock is not None:
            with contextlib.suppress(OSError):
                self._sock.close()
            self._sock = None

    def authenticate(self, password: str) -> None:
        """Authenticate with the RCON server.

        Raises AuthenticationError if the server rejects the password.
        """
        request_id = next(_request_id_counter)
        self._send(
            Packet(
                request_id=request_id,
                packet_type=PacketType.LOGIN,
                payload=password,
            )
        )
        response = self._recv()
        if response.request_id == -1:
            msg = "Authentication failed: incorrect RCON password"
            raise AuthenticationError(msg)

    def command(self, cmd: str) -> str:
        """Send a command and return the full response text.

        Uses the sentinel technique for multi-packet responses: after sending
        the real command, a follow-up empty packet is sent. Responses are
        collected until the sentinel packet's response arrives.
        """
        request_id = next(_request_id_counter)

        # Send the actual command
        self._send(
            Packet(
                request_id=request_id,
                packet_type=PacketType.COMMAND,
                payload=cmd,
            )
        )

        # Send a follow-up sentinel packet. The server processes packets in
        # order, so when we receive the response to this sentinel, all response
        # packets for the real command have already arrived.
        self._send(
            Packet(
                request_id=_SENTINEL_ID,
                packet_type=PacketType.COMMAND,
                payload="",
            )
        )

        fragments: list[str] = []
        while True:
            try:
                response = self._recv()
            except TimeoutError:
                # If things time out waiting for the sentinel, return what we have
                break

            if response.request_id == _SENTINEL_ID:
                break
            if response.request_id == request_id:
                fragments.append(response.payload)

        return "".join(fragments)

    def _send(self, packet: Packet) -> None:
        """Send an encoded packet over the socket."""
        if self._sock is None:
            msg = "Not connected"
            raise ConnectionError(msg)
        try:
            self._sock.sendall(packet.encode())
        except OSError as e:
            self.close()
            msg = f"Failed to send data: {e}"
            raise ConnectionError(msg) from e

    def _recv(self) -> Packet:
        """Receive a single packet from the socket."""
        length_data = self._recv_exact(4)
        (length,) = struct.unpack("<i", length_data)
        body = self._recv_exact(length)
        return Packet.decode(body)

    def _recv_exact(self, num_bytes: int) -> bytes:
        """Read exactly num_bytes from the socket, handling partial reads."""
        if self._sock is None:
            msg = "Not connected"
            raise ConnectionError(msg)

        data = bytearray()
        while len(data) < num_bytes:
            try:
                chunk = self._sock.recv(num_bytes - len(data))
            except TimeoutError:
                raise
            except OSError as e:
                self.close()
                msg = f"Connection lost: {e}"
                raise ConnectionError(msg) from e

            if not chunk:
                self.close()
                msg = "Connection closed by server"
                raise ConnectionError(msg)

            data.extend(chunk)

        return bytes(data)
