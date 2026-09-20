"""UI setup for the PAL TOUCH-5 controller."""

from __future__ import annotations

import ipaddress
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_MAC, CONF_REQUEST_PREFIX, DOMAIN
from .protocol import ProtocolError, Touch5Client, hello_frame, normalize_mac

_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Required(CONF_MAC): TextSelector(),
        vol.Required(CONF_REQUEST_PREFIX): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class PalTouch5ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up one controller through the Home Assistant UI."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Validate settings with a non-actuating 0x23 handshake."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                host = str(ipaddress.IPv4Address(user_input[CONF_HOST]))
                mac = normalize_mac(user_input[CONF_MAC])
                request_prefix = bytes.fromhex(user_input[CONF_REQUEST_PREFIX])
                hello_frame(1, request_prefix)
            except (ValueError, KeyError):
                errors["base"] = "invalid_settings"
            else:
                client = Touch5Client(host, mac, request_prefix)
                try:
                    await self.hass.async_add_executor_job(client.probe)
                except (OSError, ProtocolError):
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="PAL TOUCH-5",
                        data={
                            CONF_HOST: host,
                            CONF_MAC: mac,
                            CONF_REQUEST_PREFIX: request_prefix.hex(),
                        },
                    )
        return self.async_show_form(step_id="user", data_schema=_SCHEMA, errors=errors)
