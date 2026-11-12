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

**Early version (0.2.1).** Tested against one A16 (firmware 2.17) in Home
Assistant 2026.11. Expect rough edges and please report issues.

### Entities

| Entity | What it does |
|---|---|
| `media_player` Realiser A16 | power on / standby and source selection (eARC, HDMI 1–4, USB, Line, Stereo, Coaxial, Optical) for the whole device |
| `media_player` User A / User B | volume and mute per user; on/off follows the device |
| `number` Volume A / Volume B | volume as shown on the A16 (27–99) |
| `select` Preset A / Preset B | preset 1–16; a preset shows its room/subject name once it has been active |
| `sensor` Mode | SVS / AV / MIX |
| `sensor` Head tracking mode | e.g. Gyro |
| `sensor` Firmware | diagnostic |

The volume slider of the media players works in percent of the A16 range
(0 % = 27, 100 % = 99). Use the *Volume* numbers for the value shown on the
A16.

Changes made with the IR remote are pushed by the A16 and show up in Home
Assistant right away (with *TCP slave response* enabled).

### Good to know

- **One controller at a time:** the A16 accepts only one TCP connection.
  While Home Assistant is connected, other control apps (e.g. Centro
  Control) cannot connect, and the other way round. After another app
  disconnects, the A16 may refuse new connections for about a minute.
- **Volume is set step by step:** the protocol has no absolute volume
  command and the A16 accepts about one command per second, so a large
  volume change takes a while (about 1.5 s per step). It runs in the
  background; a newer target replaces an older one.
- **Power on takes ~65 s:** while the A16 boots, the player shows *on* with
  the attribute `power_state: boot`.
- **Mute state:** the A16 reports it only when it is toggled. Until then it is
  unknown.
- **Diagnostics:** the device page offers a diagnostics download with
  connection statistics (response times, lost or ignored commands).
- IR remote keys and a dedicated sidebar panel are planned, see
  [docs/roadmap.md](docs/roadmap.md).

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
