"""PAL app wheel-position control for the TOUCH-5 CH5 lights."""

from __future__ import annotations

import math

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Touch5Hub
from .const import DOMAIN
from .palette import wheel_angle_to_byte
from .protocol import ProtocolError


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a wheel-position control; saturation and brightness are unsupported."""
    async_add_entities([Touch5WheelPosition(entry.runtime_data)])


class Touch5WheelPosition(RestoreNumber):
    """Show the last commanded wheel position, not a measured color."""

    _attr_assumed_state = True
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Pool/spa light wheel position"
    _attr_icon = "mdi:palette"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 0
    _attr_native_max_value = 359
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "°"

    def __init__(self, hub: Touch5Hub) -> None:
        self._hub = hub
        self._attr_unique_id = f"{hub.mac}_ch5_wheel_position"
        self._attr_native_value: float | None = None
        self._state_source = "unknown"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, hub.mac)},
            "name": "PAL TOUCH-5",
            "manufacturer": "PAL Lighting",
            "model": "TOUCH-5",
        }

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Identify this as approximate, last-commanded state."""
        return {
            "state_source": self._state_source,
            "physical_color": "not_reported_by_controller",
            "palette_calibration": "six_app_observed_clock_positions_interpolated",
        }

    async def async_added_to_hass(self) -> None:
        """Restore display-only position history without sending a command."""
        await super().async_added_to_hass()
        previous = await self.async_get_last_number_data()
        if previous and previous.native_value is not None:
            value = previous.native_value
            if math.isfinite(value) and 0 <= value <= 359:
                self._attr_native_value = value
                self._state_source = "restored_last_command"

    async def async_set_native_value(self, value: float) -> None:
        """Send one wheel-position command. Power remains a separate entity."""
        if not math.isfinite(value) or not 0 <= value <= 359:
            raise HomeAssistantError("Wheel angle must be between 0 and 359 degrees")
        angle = round(value)
        try:
            await self._hub.set_light_color(self.hass, wheel_angle_to_byte(angle))
        except (OSError, ProtocolError) as error:
            self._attr_native_value = None
            self._state_source = "command_not_acknowledged"
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"PAL TOUCH-5 color command not acknowledged: {error}"
            ) from error
        self._attr_native_value = angle
        self._state_source = "last_acknowledged_command"
        self.async_write_ha_state()
