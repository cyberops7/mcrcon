"""Tests for the RCON wire protocol."""

import struct

from mcrcon.protocol import Packet, PacketType


class TestPacketEncode:
    def test_login_packet(self):
        packet = Packet(request_id=1, packet_type=PacketType.LOGIN, payload="password")
        data = packet.encode()

        # Parse the encoded data
        length = struct.unpack_from("<i", data, 0)[0]
        request_id = struct.unpack_from("<i", data, 4)[0]
        packet_type = struct.unpack_from("<i", data, 8)[0]

        assert request_id == 1
        assert packet_type == PacketType.LOGIN
        # Length = 4 (req_id) + 4 (type) + len("password") + 2 (nulls)
        assert length == 4 + 4 + 8 + 2

    def test_command_packet(self):
        packet = Packet(request_id=42, packet_type=PacketType.COMMAND, payload="list")
        data = packet.encode()

        length = struct.unpack_from("<i", data, 0)[0]
        request_id = struct.unpack_from("<i", data, 4)[0]
        packet_type = struct.unpack_from("<i", data, 8)[0]

        assert request_id == 42
        assert packet_type == PacketType.COMMAND
        assert length == 4 + 4 + 4 + 2

    def test_empty_payload(self):
        packet = Packet(request_id=1, packet_type=PacketType.COMMAND, payload="")
        data = packet.encode()

        length = struct.unpack_from("<i", data, 0)[0]
        assert length == 4 + 4 + 0 + 2

    def test_trailing_null_bytes(self):
        packet = Packet(request_id=1, packet_type=PacketType.COMMAND, payload="test")
        data = packet.encode()

        # The last two bytes should be null
        assert data[-2:] == b"\x00\x00"


class TestPacketDecode:
    def test_decode_response(self):
        # Build raw body bytes (without length prefix)
        request_id = 1
        packet_type = PacketType.RESPONSE
        payload = "There are 3 of a max of 20 players online"
        body = struct.pack("<ii", request_id, packet_type)
        body += payload.encode("utf-8") + b"\x00\x00"

        packet = Packet.decode(body)
        assert packet.request_id == 1
        assert packet.packet_type == PacketType.RESPONSE
        assert packet.payload == payload

    def test_decode_empty_payload(self):
        body = struct.pack("<ii", 5, PacketType.RESPONSE) + b"\x00\x00"
        packet = Packet.decode(body)

        assert packet.request_id == 5
        assert packet.payload == ""

    def test_decode_auth_failure(self):
        # Server sends request_id == -1 on auth failure
        body = struct.pack("<ii", -1, PacketType.COMMAND) + b"\x00\x00"
        packet = Packet.decode(body)

        assert packet.request_id == -1


class TestPacketRoundTrip:
    def test_roundtrip(self):
        original = Packet(
            request_id=7,
            packet_type=PacketType.COMMAND,
            payload="gamemode creative Steve",
        )
        encoded = original.encode()
        # Skip the 4-byte length prefix for decode
        decoded = Packet.decode(encoded[4:])

        assert decoded.request_id == original.request_id
        assert decoded.packet_type == original.packet_type
        assert decoded.payload == original.payload

    def test_roundtrip_unicode(self):
        original = Packet(
            request_id=1,
            packet_type=PacketType.COMMAND,
            payload="say Hello \u00e9\u00e8\u00ea",
        )
        encoded = original.encode()
        decoded = Packet.decode(encoded[4:])

        assert decoded.payload == original.payload
