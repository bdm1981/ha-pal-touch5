"""Offline tests for the app-observed PAL wheel mapping."""

from __future__ import annotations

import math
import unittest

from custom_components.pal_touch5.palette import wheel_angle_to_byte


class PaletteTests(unittest.TestCase):
    def test_six_app_observed_clock_positions(self) -> None:
        self.assertEqual(
            [wheel_angle_to_byte(angle) for angle in range(0, 360, 60)],
            [0xFF, 0x2A, 0x5E, 0x7E, 0xB1, 0xDD],
        )

    def test_wrap_and_intermediate_positions(self) -> None:
        self.assertEqual(wheel_angle_to_byte(360), 0xFF)
        self.assertEqual(wheel_angle_to_byte(30), 0x14)
        self.assertTrue(
            all(0 <= wheel_angle_to_byte(angle) <= 255 for angle in range(360))
        )

    def test_nonfinite_angle_rejected(self) -> None:
        for angle in (math.inf, -math.inf, math.nan):
            with self.assertRaises(ValueError):
                wheel_angle_to_byte(angle)
