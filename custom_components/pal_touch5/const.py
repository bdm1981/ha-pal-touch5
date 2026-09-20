"""Constants for the PAL TOUCH-5 integration."""

DOMAIN = "pal_touch5"
CONF_MAC = "mac"
CONF_REQUEST_PREFIX = "request_prefix"
UDP_PORT = 5987

# These mappings were confirmed from the PAL iOS app's 0x80 frames.
RELAY_NAMES = {
    1: "Hot tub pump",
    2: "Hot tub heater",
    3: "Hot tub blower",
}
