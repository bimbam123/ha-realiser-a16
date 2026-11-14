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

## v0.2.1 – feedback from the first installation (released)

- Power and source on a device-level media player ("Realiser A16"); the
  user players only have volume and mute (power applies to the whole device)
- User B: media player, volume number and preset select; room/subject of B
  are queried with `a0` after a preset change (B is not pushed)
- Volume numbers 27–99 per user (the media player slider works in %)
- More robust volume stepping: 2.5 s between steps, up to five ignored steps
  per target
- "Reconfigure" for IP address and port (replaces the port option)
- Diagnostics download with connection statistics

## v0.2.2 – volume like on the A16 display (released)

- The user players show the volume 1:1 with the A16 display (64 = 64 %,
  range 27–99); volume up/down is exactly one A16 step
- The number entities "Volume A/B" of v0.2.1 are removed (duplicates); their
  registry entries are cleaned up on setup

## v0.3.0 – more controls and sensors

- `select` **Source** (same state as the source of the device player, for
  dashboards)
- `select` **Output**: headphones (`4d`) / speakers (`5e`); the mode sensor
  (SVS/AV/MIX) becomes a diagnostic entity
- `switch` **Test signal** (`08`, state from `af`)
- `button` **HT display** (`42`): toggles the head-tracker angle display; a
  button because a remote HT press is not pushed (b1 had a switch "Head
  tracking", removed in b2)
- Toggles are never repeated blindly: an unanswered toggle was ignored by the
  A16 (checked with a query where there is one) and is sent once more
- Sensors: decoder, listening mode, upmixer; diagnostic: legacy decoding,
  single/dual user, HPEQ A/B (subject, type, date, headphone as attributes),
  tactile A/B

## v0.4 – Realiser panel and dashboard cards

Built in three steps, each tested on the device before the next one:
1. panel and control card
2. speaker grid with solo/mute
3. level meters and tracker

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
| **Control** | Fig. 1/10 main page | power, source buttons (eARC, HDMI 1–4, Coax, Line, Optical, USB, Stereo), per user: preset grid 1–16 with learned names, volume with +/−, mute; info fields: room, layout, subject, HPEQ file/subject/date/type, headphone, tactile; header: audio/decoder, upmixer, format/listening mode, users, legacy, HT mode | `realiser-a16-control-card` (option: user A, B or both) |
| **Speaker map** | Fig. 12 solo/mute page | grid of 7 × 9 cells from Table 4 (`pya16.speakers.grid()`), cell = designator, colour = layer; only speakers visible in the current layout (`Vnn`) are shown; state active/muted (`Ann`/`Mnn`); tap = select speaker (`b1`–`e2`); ALL (solo ↔ mute, `1a`), TEST (`08`), SVS/stereo; layout name above the grid | `realiser-a16-speaker-map-card` |
| **Tracker** | TRACKER | HT display (`42`), HT mode, HT angle user A/B (`85`/`a5`, live) | `realiser-a16-tracker-card` |
| **Meters** | Fig. 11 meters | 24 channel levels per user plus HP L/R and TACT L/R (`6a`, live), labels from the channel assignment (`37`), reset (`38`) | `realiser-a16-meters-card` |
| **About** | ABOUT | firmware A16/APM/HSR/HT, serial number, connection state, link to docs | part of the panel only |

### Architecture

- **Backend (integration)**
  - WebSocket API, admin only:
    - `realiser_a16/subscribe`: state snapshot plus changes
    - `realiser_a16/command`: allow-listed commands only, never raw codes from
      the browser
    - `realiser_a16/live`: start/stop live values
  - **Priority:** operating commands (volume, source, presets, toggles)
    always go before live queries in the command queue, so the panel never
    makes the controls slow.
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

### Prerequisites / open questions

- **Mute B, solo/mute speakers:** query and toggle semantics still
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
- IR remote keys as `button` entities (menu, arrows, ENTER, BACK, …)
- More translations
- AV mode: in AV mode user A volume sets the line output and user B is not
  valid (manual 9.4.4.2); show this on the user B player
- Output select: AV can only be engaged if enabled in the preset and A/B demo
  mode is off (manual 9.4.4.4), otherwise `5e` gives `MIX`; explain this
- A/B demo mode: check whether a head-top tilt (SVS ↔ AV) pushes `MODE=`
- Remote key presses as an `event` entity: not possible for PA and HT (no
  `KEY=` push), maybe for other keys
- HPB→A (manual 9.4.4.10): compare two presets on headphone A
  (RIGHT/LEFT on the user A speaker map)
- Display page control: PA/PB cycles speaker map, input meters, output
  meters; `PAGE=` is parsed but unused
- Firmware APM/HSR/HT and serial as diagnostic entities
- Tri-Ref volume (`TRI=1..3`): with Tri-Ref enabled a volume step cycles
  between three levels, which the volume target does not handle (see
  `docs/protocol.md`)
