# PAL TOUCH-5 for Home Assistant

Experimental, local-only Home Assistant integration for PAL TOUCH-5 controllers.
This is **not** the community `pallight` integration, which targets a different
frame format. No cloud account is needed.

## Current scope

- CH1: hot-tub pump relay (verified)
- CH2: hot-tub heater relay (verified; entity disabled by default)
- CH3: hot-tub blower relay (verified)
- CH4: not exposed; the connected load is not confirmed
- CH5: pool/spa light ON/OFF (verified)

The color frame's red command was verified on this installation. A published
color-wheel mapping for another PAL controller did not work here: a blue
request remained red. Color control is therefore withheld from the Home
Assistant light entity until this Touch-5's own app traffic is captured and
the mapping physically verified.

The controller ACKs commands but does **not** report reliable physical relay
state. Switches therefore show the last acknowledged command as an assumed
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
