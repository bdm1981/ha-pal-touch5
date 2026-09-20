"""Relay switches for the PAL TOUCH-5 controller."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import Touch5Hub
from .const import RELAY_NAMES, DOMAIN
from .protocol import ProtocolError

_ICONS = {1: "mdi:pump", 2: "mdi:water-boiler", 3: "mdi:fan"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create only the three physically mapped relay entities."""
    hub: Touch5Hub = entry.runtime_data
    async_add_entities(Touch5Relay(hub, channel) for channel in RELAY_NAMES)


class Touch5Relay(SwitchEntity, RestoreEntity):
    """Switch reporting its last acknowledged command, not relay telemetry."""

    _attr_assumed_state = True
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: Touch5Hub, channel: int) -> None:
        """Keep all device I/O out of entity property getters."""
        self._hub = hub
        self._channel = channel
        self._is_on: bool | None = None
        self._state_source = "unknown"
        self._attr_name = RELAY_NAMES[channel]
        self._attr_unique_id = f"{hub.mac}_ch{channel}"
        self._attr_icon = _ICONS[channel]
        self._attr_device_info = {
            "identifiers": {(DOMAIN, hub.mac)},
            "name": "PAL TOUCH-5",
            "manufacturer": "PAL Lighting",
            "model": "TOUCH-5",
        }
        # Heater control requires a verified independent flow/pressure safety
        # interlock before the user explicitly enables it in the entity registry.
        self._attr_entity_registry_enabled_default = channel != 2

    @property
    def is_on(self) -> bool | None:
        """Return the last command state, or unknown before any known command."""
        return self._is_on

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Make the absence of physical feedback clear in entity details."""
        return {
            "state_source": self._state_source,
            "physical_state": "not_reported_by_controller",
        }

    async def async_added_to_hass(self) -> None:
        """Restore display-only history; never replay an ON command."""
        await super().async_added_to_hass()
        previous = await self.async_get_last_state()
        if previous and previous.state in ("on", "off"):
            self._is_on = previous.state == "on"
            self._state_source = "restored_last_command"

    async def _set(self, turn_on: bool) -> None:
        try:
            await self._hub.set_relay(self.hass, self._channel, turn_on)
        except (OSError, ProtocolError) as error:
            self._is_on = None
            self._state_source = "command_not_acknowledged"
            self.async_write_ha_state()
            raise HomeAssistantError(f"PAL TOUCH-5 command not acknowledged: {error}") from error
        self._is_on = turn_on
        self._state_source = "last_acknowledged_command"
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send ON once; the ACK does not prove physical relay position."""
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send OFF once; the ACK does not prove physical relay position."""
        await self._set(False)
