"""PAL TOUCH-5 app wheel position to device byte mapping.

Six anchor packets were captured directly from the user's TOUCH-5 app at
12, 2, 4, 6, 8, and 10 o'clock. Intermediate positions are interpolated;
they have not been physically calibrated one by one. No session bytes or
private network details are stored here.
"""

from __future__ import annotations

import math

# Angle 0 is the top of the PAL app wheel; values increase clockwise.
# Device bytes are unwrapped across 0xff -> 0x00 for interpolation.
_ANCHORS: tuple[tuple[int, int], ...] = (
    (0, 0xFF),      # 12 o'clock
    (60, 0x12A),   # 2 o'clock: 0x2a
    (120, 0x15E),  # 4 o'clock: 0x5e
    (180, 0x17E),  # 6 o'clock: 0x7e
    (240, 0x1B1),  # 8 o'clock: 0xb1
    (300, 0x1DD),  # 10 o'clock: 0xdd
    (360, 0x1FF),  # 12 o'clock again: 0xff
)


def wheel_angle_to_byte(angle: float) -> int:
    """Map a clockwise 0–359° PAL app wheel angle onto its raw color byte."""
    if not math.isfinite(angle):
        raise ValueError("Wheel angle must be finite")
    normalized = angle % 360
    for (start_angle, start_byte), (end_angle, end_byte) in zip(
        _ANCHORS, _ANCHORS[1:]
    ):
        if normalized <= end_angle:
            fraction = (normalized - start_angle) / (end_angle - start_angle)
            return round(start_byte + fraction * (end_byte - start_byte)) % 256
    raise AssertionError("Angle anchor table does not cover the full wheel")
