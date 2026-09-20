# PAL TOUCH-5 for Home Assistant

Experimental, local-only Home Assistant integration for PAL TOUCH-5 controllers.
This is **not** the community `pallight` integration, which targets a different
frame format. No cloud account is needed.

## Current scope

- CH1: hot-tub pump relay (verified)
- CH2: hot-tub heater relay (verified; entity disabled by default)
- CH3: hot-tub blower relay (verified)
- CH4: not exposed; the connected load is not confirmed
- CH5: pool/spa light ON/OFF and Red/Green/Blue color presets (verified)
- CH5 color wheel: a 0–359° PAL-app wheel-position control and optional
  dashboard card; six clock positions were captured on this TOUCH-5

The TOUCH-5 app's CH5 ON/OFF and color frames were captured directly. Red, green,
and blue bytes from the community `pallight` map also produced the expected
physical colors when sent in that TOUCH-5 frame. The Home Assistant selector
exposes those verified presets. The wheel-position number entity reproduces
the PAL app's wheel from six directly captured clock positions. Values between
the captured positions are interpolated, so exact shades may differ slightly.
Turn the light on before selecting a color. Saturation and absolute brightness
are not exposed: Home Assistant's native HS light mode implies controls this
controller has not yet been shown to support.

To use the optional wheel card, add a dashboard resource of type **JavaScript
module** with URL `/pal_touch5/pal-touch5-wheel.js?v=0.3.0`, then add a Manual
card with the entity IDs from your own PAL device:

```yaml
type: custom:pal-touch5-wheel-card
entity: number.your_pool_spa_light_wheel_position
light: light.your_pool_spa_lights
```

The card sends one color command on release, rather than flooding the controller
while you drag. It has keyboard arrow-key support. The wheel and position number
show the last acknowledged command, not a physical color measurement. The
PAL app or another controller can make their display stale. Changing the
Red/Green/Blue preset does not update the wheel-position number's display,
or vice versa.

The controller ACKs commands but does **not** report reliable physical relay
state. Switches and color controls therefore show the last acknowledged command as an assumed
state. A restored state after Home Assistant restarts is display-only: this
integration never replays an ON command at startup. Commands issued through
the PAL app or another controller can make Home Assistant's displayed state
stale. A missing ACK is an unknown physical state, not proof that the command
failed to actuate the relay.

## Safety boundary

Do not treat a 15-second pump delay or a last-commanded pump state as proof
of water flow. The heater must have a functioning independent flow/pressure
interlock and its manufacturer's operating requirements must be followed.
The heater entity is disabled by default pending that confirmation. Do not
use this experimental version unattended. A restart-safe shutdown cooldown
automation has **not** been installed yet.

## Private setup data

The controller IPv4 address, MAC address, and 22-byte session request prefix
are entered in Home Assistant's setup UI; none is stored in this repository.
Treat the prefix as a credential until proven otherwise. Never commit packet
captures, Home Assistant storage, `secrets.yaml`, or local configuration to
this public repo. The setup flow only performs a non-actuating handshake.

## Development

Run the protocol tests without Home Assistant or network access:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q custom_components tests
```

The integration source lives at `custom_components/pal_touch5/`, following
Home Assistant's custom integration layout. Copy that directory to the Home
Assistant instance's `/config/custom_components/` and restart Home Assistant.
