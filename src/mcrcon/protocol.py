"""Minecraft RCON wire protocol encoding and decoding."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum


class PacketType(IntEnum):
    """RCON packet types."""

    RESPONSE = 0
    COMMAND = 2
    LOGIN = 3


# 4 bytes each for length, request_id, and type
HEADER_SIZE = 12
MAX_PAYLOAD = 4096


@dataclass(frozen=True)
class Packet:
    """A single RCON packet.

    Wire format: [length:i32][request_id:i32][type:i32][payload\\0\\0]
    Length covers everything after itself (req_id + type + payload + 2 nulls).
    """

    request_id: int
    packet_type: int
    payload: str

    def encode(self) -> bytes:
        """Encode the packet into bytes for transmission."""
        payload_bytes = self.payload.encode("utf-8") + b"\x00\x00"
        length = 4 + 4 + len(payload_bytes)
        return struct.pack(
            f"<iii{len(payload_bytes)}s",
            length,
            self.request_id,
            self.packet_type,
            payload_bytes,
        )

    @classmethod
    def decode(cls, data: bytes) -> Packet:
        """Decode a packet from raw bytes (excluding the 4-byte length prefix).

        The caller is responsible for reading the 4-byte length prefix and then
        reading exactly that many bytes before passing them here.
        """
        request_id, packet_type = struct.unpack_from("<ii", data, 0)
        payload = data[8:-2].decode("utf-8", errors="replace")
        return cls(
            request_id=request_id,
            packet_type=packet_type,
            payload=payload,
        )
