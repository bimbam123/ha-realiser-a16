# Roadmap

Unofficial integration, not affiliated with Smyth Research. Versions are
plans, not promises.

## v0.2.0 – first integration (released)

- Push coordinator, exactly one TCP connection per device (`pya16`)
- Config flow (host, port, connection test, serial as unique ID), port option
- `media_player` user A: power, volume 27–99 (target in the background,
  latest target wins), volume steps, mute with state check, sources
- `select` preset A (1–16, names learned when a preset was active)
- Sensors: mode (SVS/AV/MIX), head tracking mode, firmware
- Entities unavailable while disconnected; `PWR=BOOT` shown as on with
  attribute `power_state: boot`

## v0.2.1 – feedback from the first installation

- Power and source on a device-level media player ("Realiser A16"); the
  user players only have volume and mute (power applies to the whole device)
- User B: media player, volume number and preset select; room/subject of B
  are queried with `a0` after a preset change (B is not pushed)
- Volume numbers 27–99 per user (the media player slider works in %)
- More robust volume stepping: 2.5 s between steps, up to five ignored steps
  per target
- "Reconfigure" for IP address and port (replaces the port option)
- Diagnostics download with connection statistics

## v0.2.2 – one control per function

- Volume per user only as `number` (27–99, the values shown on the A16);
  the per-user media players (volume in %) are removed
- Mute per user as `switch`
- Old user media player entities are removed from the entity registry

## v0.3 – Realiser panel and dashboard cards

### Goal

A dedicated **sidebar entry** ("Realiser A16"), similar to Alarmo, which
follows the structure and categories of the manufacturer's Centro Control
example app (PDF Fig. 1, 10–12), including the **speaker grid for
solo/mute**. Every building block is also available as a separate **Lovelace
dashboard card**.

### Pages / building blocks

The categories follow the Centro app (navigation CONTROL, SPKR MAP, TRACKER,
METERS, ABOUT).

| Building block | Centro equivalent | Contents | Card |
|---|---|---|---|
| **Control** | Fig. 1/10 main page | power, source buttons (eARC, HDMI 1–4, Coax, Line, Optical, USB, Stereo), per user: preset grid 1–16 with learned names, volume with +/−, tri-level 1/2/3 (user A), mute; info fields: room, layout, subject, HPEQ file/subject/date/type, headphone, tactile; header: audio/decoder, upmixer, format/listening mode, users, legacy, HT mode | `realiser-a16-control-card` (option: user A, B or both) |
| **Speaker map** | Fig. 12 solo/mute page | grid of 7 × 9 cells from Table 4 (`pya16.speakers.grid()`), cell = designator, colour = layer; only speakers visible in the current layout (`Vnn`) are shown; state active/muted (`Ann`/`Mnn`); tap = select speaker (`b1`–`e2`); ALL (solo ↔ mute, `1a`), TEST (`08`), SVS/stereo; layout name above the grid | `realiser-a16-speaker-map-card` |
| **Tracker** | TRACKER | head tracking on/off (`42`), HT mode, HT angle user A/B (`85`/`a5`, live) | `realiser-a16-tracker-card` |
| **Meters** | Fig. 11 meters | 24 channel levels per user plus HP L/R and TACT L/R (`6a`, live), labels from the channel assignment (`37`), reset (`38`) | `realiser-a16-meters-card` |
| **About** | ABOUT | firmware A16/APM/HSR/HT, serial number, connection state, link to docs | part of the panel only |

### Architecture

- **Backend (integration)**
  - WebSocket API, admin only:
    - `realiser_a16/subscribe`: state snapshot plus changes
    - `realiser_a16/command`: allow-listed commands only, never raw codes from
      the browser
    - `realiser_a16/live`: start/stop live values
  - **Live mode:** meters (`6a`) and HT angle (`85`/`a5`) are not pushed by
    the A16. They are polled **only while a panel or card subscribes to them**,
    rate-limited and through the same command queue. Polling at 2 Hz like the
    Centro app is not possible with our serial queue. The device needs
    0.5–1.5 s per answer, so the achievable rate has to be measured
    (preferably over a wired network). Live values are not stored as HA
    entities, so the recorder stays clean.
  - Panel registration with `panel_custom` (sidebar entry, icon, admin only),
    JS served from the integration folder via `async_register_static_paths`.
  - Cards registered with `frontend.add_extra_js_url`, so no manual resource
    setup is needed.
- **Frontend**
  - Lit + TypeScript web components, one per building block; the panel
    composes the same components.
  - Built bundle inside `custom_components/realiser_a16/frontend/`
    (Marketplace rule: everything inside the integration folder). The build
    tooling (rollup) lives in `frontend/` at the repo root.
  - Translations de/en, HA theme variables, works on mobile.
  - Visual card editors (`getConfigElement`) for picking the device and
    the user.
- **Data**
  - Speaker table and grid from `pya16.speakers` (sent once to the frontend),
    preset names from the coordinator store.

### Prerequisites from v0.2 / open questions

- **Mute B, tri-level, solo/mute speakers:** query and toggle semantics still
  need to be tested on the device. `Ann`/`Mnn` come only from `af` and the
  speaker select commands.
- **Live rates:** measure the achievable rate of `6a`/`85` and how many
  commands are dropped at that rate.
- **Speaker grid:** layouts with more than 16 channels (the user A DSP
  reports only 16 assignments, e.g. layout 12.1.10) need a check of what
  `ae` reports.
- **Branding:** no Smyth or Centro logos or artwork; own icons only.

## Later (unordered)

- Diagnostics download (state, anonymised)
- Repairs issue when another controller blocks the only connection
- Actions for raw commands (advanced, admin only)
- Submission to the default Marketplace catalog (hacs/default)
