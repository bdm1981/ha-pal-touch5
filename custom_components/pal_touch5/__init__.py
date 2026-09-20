"""PAL TOUCH-5 local controller integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .const import CONF_MAC, CONF_REQUEST_PREFIX, DOMAIN
from .protocol import Touch5Client

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS = ["switch", "light", "select", "number"]
CONF_HOST = "host"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Serve the optional color-wheel card bundled with this integration."""
    from homeassistant.components.http import StaticPathConfig

    card_path = Path(__file__).parent / "frontend" / "pal-touch5-wheel.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/pal_touch5/pal-touch5-wheel.js", str(card_path), False)]
    )
    return True


@dataclass
class Touch5Hub:
    """Serialize commands to one controller."""

    client: Touch5Client
    mac: str
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def set_relay(self, hass: HomeAssistant, channel: int, turn_on: bool) -> None:
        """Run blocking UDP exchange outside the HA event loop."""
        async with self.lock:
            await hass.async_add_executor_job(self.client.set_relay, channel, turn_on)

    async def set_light_power(self, hass: HomeAssistant, turn_on: bool) -> None:
        """Serialize CH5 light commands with the equipment relays."""
        async with self.lock:
            await hass.async_add_executor_job(self.client.set_light_power, turn_on)

    async def set_light_color(self, hass: HomeAssistant, hue_byte: int) -> None:
        """Serialize a verified CH5 color command with other commands."""
        async with self.lock:
            await hass.async_add_executor_job(self.client.set_light_color_byte, hue_byte)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entities. Never issue a relay command at startup."""
    client = Touch5Client(
        host=entry.data[CONF_HOST],
        mac=entry.data[CONF_MAC],
        request_prefix=bytes.fromhex(entry.data[CONF_REQUEST_PREFIX]),
    )
    entry.runtime_data = Touch5Hub(client=client, mac=entry.data[CONF_MAC])
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration without changing controller outputs."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
