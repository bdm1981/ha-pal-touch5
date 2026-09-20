"""CH5 pool/spa light for the PAL TOUCH-5 controller."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import Touch5Hub
from .const import DOMAIN
from .protocol import ProtocolError


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the verified CH5 light entity."""
    async_add_entities([Touch5Light(entry.runtime_data)])


class Touch5Light(LightEntity, RestoreEntity):
    """On/off light that reports the last acknowledged command only."""

    _attr_assumed_state = True
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF
    _attr_icon = "mdi:pool"
    _attr_name = "Pool/spa lights"

    def __init__(self, hub: Touch5Hub) -> None:
        self._hub = hub
        self._attr_unique_id = f"{hub.mac}_ch5"
        self._attr_is_on: bool | None = None
        self._state_source = "unknown"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, hub.mac)},
            "name": "PAL TOUCH-5",
            "manufacturer": "PAL Lighting",
            "model": "TOUCH-5",
        }

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Make the lack of physical feedback visible to users."""
        return {
            "state_source": self._state_source,
            "physical_state": "not_reported_by_controller",
        }

    async def async_added_to_hass(self) -> None:
        """Restore display-only history; do not switch lights at startup."""
        await super().async_added_to_hass()
        previous = await self.async_get_last_state()
        if previous and previous.state in ("on", "off"):
            self._attr_is_on = previous.state == "on"
            self._state_source = "restored_last_command"

    async def _set(self, turn_on: bool) -> None:
        try:
            await self._hub.set_light_power(self.hass, turn_on)
        except (OSError, ProtocolError) as error:
            self._attr_is_on = None
            self._state_source = "command_not_acknowledged"
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"PAL TOUCH-5 light command not acknowledged: {error}"
            ) from error
        self._attr_is_on = turn_on
        self._state_source = "last_acknowledged_command"
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send CH5 ON without assuming physical feedback."""
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send CH5 OFF without assuming physical feedback."""
        await self._set(False)
