"""Minimal, local PAL TOUCH-5 Xlink UDP protocol.

This is separate from Home Assistant so packet construction and response
handling can be tested without connecting to physical equipment.
"""

from __future__ import annotations

import secrets
import socket
import time
from dataclasses import dataclass, field

from .const import UDP_PORT

_COMMAND_BODY = bytes.fromhex("a100000503")


class ProtocolError(Exception):
    """The controller did not provide a valid response."""


def normalize_mac(value: str) -> str:
    """Return a 12-digit uppercase MAC, rejecting malformed values."""
    compact = value.replace(":", "").replace("-", "").upper()
    if len(compact) != 12 or any(c not in "0123456789ABCDEF" for c in compact):
        raise ValueError("Expected a 12-digit MAC address")
    return compact


def hello_frame(source_port: int, request_prefix: bytes) -> bytes:
    """Build the 0x23 request using a locally configured prefix.

    The 22-byte prefix might contain device-specific credentials, so no
    captured value is included in this public source tree.
    """
    if not 1 <= source_port <= 65535:
        raise ValueError("Invalid UDP source port")
    if len(request_prefix) != 22 or request_prefix[:5] != bytes.fromhex("2300000016"):
        raise ValueError("Expected a 22-byte 0x23 session request prefix")
    return request_prefix + source_port.to_bytes(2, "big") + bytes.fromhex("00001e")


def parse_hello_response(frame: bytes, expected_mac: str) -> bytes:
    """Validate the observed 0x28 response and return its session token."""
    if len(frame) < 21 or frame[0] != 0x28 or frame[5:7] != b"\x00\x02":
        raise ProtocolError("Invalid session response")
    if frame[7:13].hex().upper() != normalize_mac(expected_mac):
        raise ProtocolError("Session response came from a different device")
    return frame[19:21]


def confirm_frame(token: bytes) -> bytes:
    """Build the observed 0x33 session confirmation."""
    if len(token) != 2:
        raise ValueError("Session token must be two bytes")
    frame = bytearray(18)
    frame[0] = 0x33
    frame[4] = 0x03
    frame[5:7] = token
    return bytes(frame)


def relay_frame(token: bytes, sequence: int, channel: int, turn_on: bool) -> bytes:
    """Build an observed 0x80 relay command. Channel 5 is not a relay."""
    if len(token) != 2 or not 0 <= sequence <= 65535:
        raise ValueError("Invalid session token or sequence")
    if channel not in (1, 2, 3, 4):
        raise ValueError("Relay channel must be 1 through 4")

    action = 2 * (channel - 1) + (not turn_on)
    frame = bytearray(22)
    frame[0] = 0x80
    frame[4] = 0x11
    frame[5:7] = token
    frame[7:9] = sequence.to_bytes(2, "big")
    frame[10:15] = _COMMAND_BODY
    frame[15] = action
    frame[21] = sum(frame[10:21]) & 0xFF
    return bytes(frame)


def parse_relay_ack(frame: bytes, sequence: int) -> None:
    """Raise unless an observed 0x88 ACK confirms the command sequence."""
    if len(frame) < 8 or frame[0] != 0x88 or frame[4] != 0x03:
        raise ProtocolError("Invalid relay acknowledgment")
    if frame[5:7] != sequence.to_bytes(2, "big"):
        raise ProtocolError("Relay acknowledgment has the wrong sequence")
    if frame[7] != 0:
        raise ProtocolError(f"Controller rejected command (status {frame[7]})")


def light_power_frame(token: bytes, sequence: int, turn_on: bool) -> bytes:
    """Build the app-observed 0x80 CH5 ON/OFF frame.

    The native PAL app sends A1/05/01/01 for ON and A1/05/01/02 for OFF,
    with a sequence-numbered 0x88 acknowledgment. The 0x83 frame used by
    earlier versions was ACKed but did not reliably turn this light off.
    """
    if len(token) != 2 or not 0 <= sequence <= 65535:
        raise ValueError("Invalid session token or sequence")
    frame = bytearray(22)
    frame[0] = 0x80
    frame[4] = 0x11
    frame[5:7] = token
    frame[7:9] = sequence.to_bytes(2, "big")
    frame[10] = 0xA1
    frame[13] = 5
    frame[14] = 1
    frame[15] = 1 if turn_on else 2
    frame[21] = sum(frame[10:21]) & 0xFF
    return bytes(frame)


def light_color_frame(token: bytes, sequence: int, hue_byte: int) -> bytes:
    """Build the app-observed 0x80 color frame with an unmapped wheel byte."""
    if len(token) != 2 or not 0 <= sequence <= 65535 or not 0 <= hue_byte <= 255:
        raise ValueError("Invalid session token, sequence, or hue byte")
    frame = bytearray(22)
    frame[0] = 0x80
    frame[4] = 0x11
    frame[5:7] = token
    frame[7:9] = sequence.to_bytes(2, "big")
    frame[10] = 0xA1
    frame[13] = 5
    frame[14] = 2
    frame[15:19] = bytes((hue_byte,)) * 4
    frame[21] = sum(frame[10:21]) & 0xFF
    return bytes(frame)


def parse_light_ack(frame: bytes, sequence: int) -> None:
    """Validate the app-observed 0x88 reply to a CH5 power command."""
    parse_relay_ack(frame, sequence)


@dataclass(frozen=True)
class Touch5Client:
    """Synchronous transport; call from Home Assistant's executor."""

    host: str
    mac: str
    request_prefix: bytes = field(repr=False)
    timeout: float = 2.0

    def __post_init__(self) -> None:
        normalize_mac(self.mac)
        hello_frame(1, self.request_prefix)
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")

    def _receive_kind(self, sock: socket.socket, kind: int, deadline: float) -> bytes:
        """Ignore unrelated packets until the expected frame or timeout."""
        while (remaining := deadline - time.monotonic()) > 0:
            sock.settimeout(remaining)
            try:
                packet = sock.recv(2048)
            except socket.timeout as error:
                raise ProtocolError(f"Timed out waiting for 0x{kind:02x}") from error
            if packet and packet[0] == kind:
                return packet
        raise ProtocolError(f"Timed out waiting for 0x{kind:02x}")

    def _open_session(self, sock: socket.socket) -> bytes:
        sock.send(hello_frame(sock.getsockname()[1], self.request_prefix))
        response = self._receive_kind(sock, 0x28, time.monotonic() + self.timeout)
        token = parse_hello_response(response, self.mac)
        sock.send(confirm_frame(token))
        return token

    def probe(self) -> None:
        """Perform a read-only handshake; never sends a relay command."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((self.host, UDP_PORT))
            self._open_session(sock)

    def set_relay(self, channel: int, turn_on: bool) -> None:
        """Send one relay command and require its matching ACK.

        No retry is attempted: after an ACK timeout the physical state is
        unknown, even if the packet actually reached the controller.
        """
        if channel not in (1, 2, 3, 4):
            raise ValueError("Relay channel must be 1 through 4")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((self.host, UDP_PORT))
            token = self._open_session(sock)
            sequence = secrets.randbelow(65535) + 1
            sock.send(relay_frame(token, sequence, channel, turn_on))
            deadline = time.monotonic() + self.timeout
            while True:
                ack = self._receive_kind(sock, 0x88, deadline)
                if len(ack) >= 7 and ack[5:7] != sequence.to_bytes(2, "big"):
                    continue
                parse_relay_ack(ack, sequence)
                return

    def set_light_power(self, turn_on: bool) -> None:
        """Send the native app's CH5 power command and require its ACK."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((self.host, UDP_PORT))
            token = self._open_session(sock)
            sequence = secrets.randbelow(65535) + 1
            sock.send(light_power_frame(token, sequence, turn_on))
            deadline = time.monotonic() + self.timeout
            while True:
                ack = self._receive_kind(sock, 0x88, deadline)
                if len(ack) >= 7 and ack[5:7] != sequence.to_bytes(2, "big"):
                    continue
                parse_light_ack(ack, sequence)
                return

    def set_light_color_byte(self, hue_byte: int) -> None:
        """Send a raw CH5 wheel byte for calibration, not HA user control."""
        if not 0 <= hue_byte <= 255:
            raise ValueError("Hue byte must be between 0 and 255")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((self.host, UDP_PORT))
            token = self._open_session(sock)
            sequence = secrets.randbelow(65535) + 1
            sock.send(light_color_frame(token, sequence, hue_byte))
            deadline = time.monotonic() + self.timeout
            while True:
                ack = self._receive_kind(sock, 0x88, deadline)
                if len(ack) >= 7 and ack[5:7] != sequence.to_bytes(2, "big"):
                    continue
                parse_relay_ack(ack, sequence)
                return
