<img src="https://raw.githubusercontent.com/bimbam123/ha-realiser-a16/main/custom_components/realiser_a16/brand/icon.png" alt="Integration icon" width="96" align="right">

# Smyth Realiser A16 for Home Assistant (unofficial)

> [!IMPORTANT]
> This is an **unofficial**, community-built integration. It is **not** made,
> endorsed or supported by Smyth Research. "Smyth Research" and "Realiser"
> are names/trademarks of their respective owner and are used here only to describe
> compatibility. Please do not contact Smyth Research for support with this
> integration — open an [issue](https://github.com/bimbam123/ha-realiser-a16/issues) instead.

A Home Assistant custom integration that controls the
[Smyth Realiser A16](https://smyth-research.com/) over its built-in TCP
command server (firmware 1.90 or newer).

## Status

**Early development.** The repository currently contains the integration
skeleton and the config flow (connection test via the A16 firmware-info
command). Entities are not implemented yet.

Planned:

- Power on / standby and power status
- Input source selection (eARC, HDMI 1–4, USB, Line, Stereo, Coaxial, Optical)
- Volume and mute for user A and user B
- Preset selection (1–16) for user A and user B
- Sensors for room, speaker layout, decoder, upmixer, head-tracker mode, firmware
- Buttons for the IR remote keys
- Live updates pushed by the A16 ("TCP slave response")

## Requirements

- Home Assistant 2026.11 or newer
- Realiser A16 with firmware 1.90+, connected by Ethernet
- On the A16 under **Settings > Network**:
  - a **fixed IP address** (outside your router's DHCP range)
  - **TCP command server** enabled (default port 4101)
  - **TCP slave response** enabled (recommended, needed for live updates)

## Installation

### Home Assistant Marketplace (custom repository)

1. Open **Settings > Marketplace**.
2. Add `https://github.com/bimbam123/ha-realiser-a16` as a custom repository
   with type **Integration**.
3. Install **Smyth Realiser A16** and restart Home Assistant.

### Manual

Copy `custom_components/realiser_a16` into the `custom_components` folder of
your Home Assistant configuration and restart.

## Configuration

**Settings > Devices & services > Add integration > Smyth Realiser A16**, then
enter the A16's IP address and TCP command port.

## Protocol

A summary of the A16 IP command set used by this integration is in
[docs/protocol.md](docs/protocol.md).

## License

[MIT](LICENSE)
