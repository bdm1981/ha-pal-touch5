"""Verified, full-saturation color presets for PAL TOUCH-5 CH5 lights."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import Touch5Hub
from .const import DOMAIN
from .protocol import ProtocolError

# Physically confirmed on a TOUCH-5 using the app-observed 0x80 color frame.
_COLORS = {"Red": 0xAD, "Green": 0x46, "Blue": 0xE1}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose only colors that have been physically verified."""
    async_add_entities([Touch5ColorSelect(entry.runtime_data)])


class Touch5ColorSelect(SelectEntity, RestoreEntity):
    """Set CH5 color without claiming physical color feedback."""

    _attr_assumed_state = True
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Pool/spa light color"
    _attr_icon = "mdi:palette"
    _attr_options = list(_COLORS)

    def __init__(self, hub: Touch5Hub) -> None:
        self._hub = hub
        self._attr_unique_id = f"{hub.mac}_ch5_color"
        self._attr_current_option: str | None = None
        self._state_source = "unknown"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, hub.mac)},
            "name": "PAL TOUCH-5",
            "manufacturer": "PAL Lighting",
            "model": "TOUCH-5",
        }

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Clarify that the selected color is not read back from the light."""
        return {
            "state_source": self._state_source,
            "physical_color": "not_reported_by_controller",
        }

    async def async_added_to_hass(self) -> None:
        """Restore display history without changing the physical lights."""
        await super().async_added_to_hass()
        previous = await self.async_get_last_state()
        if previous and previous.state in _COLORS:
            self._attr_current_option = previous.state
            self._state_source = "restored_last_command"

    async def async_select_option(self, option: str) -> None:
        """Send one color command; CH5 power is controlled separately."""
        if option not in _COLORS:
            raise HomeAssistantError(f"Unsupported PAL TOUCH-5 color: {option}")
        try:
            await self._hub.set_light_color(self.hass, _COLORS[option])
        except (OSError, ProtocolError) as error:
            self._attr_current_option = None
            self._state_source = "command_not_acknowledged"
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"PAL TOUCH-5 color command not acknowledged: {error}"
            ) from error
        self._attr_current_option = option
        self._state_source = "last_acknowledged_command"
        self.async_write_ha_state()
