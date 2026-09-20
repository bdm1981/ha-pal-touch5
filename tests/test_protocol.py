"""Offline tests: these must never send a network packet."""

from __future__ import annotations

import socket
import unittest
from unittest.mock import patch

from custom_components.pal_touch5.protocol import (
    ProtocolError,
    Touch5Client,
    confirm_frame,
    hello_frame,
    light_color_frame,
    light_power_frame,
    parse_hello_response,
    parse_light_ack,
    parse_relay_ack,
    relay_frame,
)

TEST_MAC = "AABBCCDDEEFF"
TEST_PREFIX = bytes.fromhex("2300000016") + bytes(17)
TEST_TOKEN = bytes.fromhex("1234")


def hello_response(mac: str = TEST_MAC) -> bytes:
    """Build a synthetic 0x28 packet, not a copied packet capture."""
    frame = bytearray(21)
    frame[0] = 0x28
    frame[5:7] = b"\x00\x02"
    frame[7:13] = bytes.fromhex(mac)
    frame[19:21] = TEST_TOKEN
    return bytes(frame)


class FakeSocket:
    """Only enough socket behavior for an offline command exchange."""

    def __init__(self, replies: list[bytes]) -> None:
        self.replies = replies
        self.sent: list[bytes] = []
        self.address: tuple[str, int] | None = None

    def __enter__(self) -> FakeSocket:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def connect(self, address: tuple[str, int]) -> None:
        self.address = address

    def getsockname(self) -> tuple[str, int]:
        return ("192.0.2.20", 43210)

    def send(self, frame: bytes) -> int:
        self.sent.append(frame)
        return len(frame)

    def settimeout(self, _seconds: float) -> None:
        return None

    def recv(self, _size: int) -> bytes:
        if not self.replies:
            raise socket.timeout()
        return self.replies.pop(0)


class ProtocolTests(unittest.TestCase):
    def test_hello_and_confirmation(self) -> None:
        self.assertEqual(len(hello_frame(43210, TEST_PREFIX)), 27)
        self.assertEqual(hello_frame(43210, TEST_PREFIX)[22:24], bytes.fromhex("a8ca"))
        self.assertEqual(parse_hello_response(hello_response(), TEST_MAC), TEST_TOKEN)
        self.assertEqual(confirm_frame(TEST_TOKEN)[:7], bytes.fromhex("33000000031234"))

    def test_reject_wrong_device(self) -> None:
        with self.assertRaises(ProtocolError):
            parse_hello_response(hello_response(), "001122334455")

    def test_relay_mapping_and_checksum(self) -> None:
        for channel in range(1, 5):
            for turn_on in (True, False):
                frame = relay_frame(TEST_TOKEN, 0x5678, channel, turn_on)
                self.assertEqual(len(frame), 22)
                self.assertEqual(frame[:5], bytes.fromhex("8000000011"))
                self.assertEqual(frame[5:9], bytes.fromhex("12345678"))
                self.assertEqual(frame[10:15], bytes.fromhex("a100000503"))
                self.assertEqual(frame[15], 2 * (channel - 1) + (not turn_on))
                self.assertEqual(frame[21], sum(frame[10:21]) & 0xFF)

    def test_ch2_on_matches_anonymized_capture_shape(self) -> None:
        self.assertEqual(
            relay_frame(TEST_TOKEN, 0x5678, 2, True).hex(),
            "80000000111234567800a100000503020000000000ab",
        )

    def test_ack_validation(self) -> None:
        parse_relay_ack(bytes.fromhex("8800000003567800"), 0x5678)
        with self.assertRaises(ProtocolError):
            parse_relay_ack(bytes.fromhex("8800000003567801"), 0x5678)
        with self.assertRaises(ProtocolError):
            parse_relay_ack(bytes.fromhex("8800000003567900"), 0x5678)

    def test_ch5_light_power_and_ack(self) -> None:
        for turn_on, action in ((True, 1), (False, 2)):
            frame = light_power_frame(TEST_TOKEN, 0x5678, turn_on)
            self.assertEqual(len(frame), 22)
            self.assertEqual(frame[:5], bytes.fromhex("8000000011"))
            self.assertEqual(frame[5:9], bytes.fromhex("12345678"))
            self.assertEqual(frame[10], 0xA1)
            self.assertEqual(frame[13:16], bytes((5, 1, action)))
            self.assertEqual(frame[21], sum(frame[10:21]) & 0xFF)
        self.assertEqual(
            light_power_frame(TEST_TOKEN, 0x5678, False).hex(),
            "80000000111234567800a100000501020000000000a9",
        )
        parse_light_ack(bytes.fromhex("8800000003567800"), 0x5678)
        with self.assertRaises(ProtocolError):
            parse_light_ack(bytes.fromhex("8800000003567801"), 0x5678)

    def test_app_observed_blue_color_frame(self) -> None:
        frame = light_color_frame(TEST_TOKEN, 0x5678, 0xFE)
        self.assertEqual(frame[:5], bytes.fromhex("8000000011"))
        self.assertEqual(frame[5:9], bytes.fromhex("12345678"))
        self.assertEqual(frame[13:19], bytes.fromhex("0502fefefefe"))
        self.assertEqual(frame[21], sum(frame[10:21]) & 0xFF)
        with self.assertRaises(ValueError):
            light_color_frame(TEST_TOKEN, 0x5678, 256)

    def test_light_sends_only_ch5_frame(self) -> None:
        fake = FakeSocket([hello_response(), bytes.fromhex("8800000003123400")])
        client = Touch5Client("192.0.2.10", TEST_MAC, TEST_PREFIX)
        with (
            patch("custom_components.pal_touch5.protocol.socket.socket", return_value=fake),
            patch("custom_components.pal_touch5.protocol.secrets.randbelow", return_value=0x1233),
        ):
            client.set_light_power(False)
        self.assertEqual([frame[0] for frame in fake.sent], [0x23, 0x33, 0x80])
        self.assertEqual(fake.sent[-1][13:16], bytes.fromhex("050102"))

    def test_color_sends_only_ch5_frame(self) -> None:
        fake = FakeSocket([hello_response(), bytes.fromhex("8800000003123400")])
        client = Touch5Client("192.0.2.10", TEST_MAC, TEST_PREFIX)
        with (
            patch("custom_components.pal_touch5.protocol.socket.socket", return_value=fake),
            patch("custom_components.pal_touch5.protocol.secrets.randbelow", return_value=0x1233),
        ):
            client.set_light_color_byte(0xFE)
        self.assertEqual([frame[0] for frame in fake.sent], [0x23, 0x33, 0x80])
        self.assertEqual(fake.sent[-1][15:19], bytes((0xFE,)) * 4)

    def test_probe_does_not_send_a_relay_command(self) -> None:
        fake = FakeSocket([hello_response()])
        client = Touch5Client("192.0.2.10", TEST_MAC, TEST_PREFIX)
        with patch("custom_components.pal_touch5.protocol.socket.socket", return_value=fake):
            client.probe()
        self.assertEqual(fake.address, ("192.0.2.10", 5987))
        self.assertEqual([frame[0] for frame in fake.sent], [0x23, 0x33])

    def test_command_sends_one_0x80_and_requires_matching_ack(self) -> None:
        fake = FakeSocket([hello_response(), bytes.fromhex("8800000003123400")])
        client = Touch5Client("192.0.2.10", TEST_MAC, TEST_PREFIX)
        with (
            patch("custom_components.pal_touch5.protocol.socket.socket", return_value=fake),
            patch("custom_components.pal_touch5.protocol.secrets.randbelow", return_value=0x1233),
        ):
            client.set_relay(2, False)
        self.assertEqual([frame[0] for frame in fake.sent], [0x23, 0x33, 0x80])
        self.assertEqual(fake.sent[-1][15], 3)


if __name__ == "__main__":
    unittest.main()
