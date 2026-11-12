# Realiser A16 IP command protocol – summary

Summarised from the manufacturer document *"Realiser A16 IP (TCP) Command
Summary"* (S. Smyth, 5 May 2020, firmware 1.90+). The original PDF is not part
of this repository. Anything marked **(unverified)** has not been tested on a
real device yet.

## Transport

| Item | Value |
|---|---|
| Transport | TCP, A16 is the server |
| Address | fixed IP set manually on the A16 (no DHCP) |
| Port | default **4101**, configurable 512–65535 |
| Enable | A16 *Settings > Network > TCP command server* (other network settings are locked while enabled) |
| Push | *TCP slave response* = A16 sends response packets on its own when a function changes (e.g. via IR remote) |
| Idle timeout | *TCP inactive timeout* 30–250 s (steps of 30 s); A16 closes idle connections |
| Status indicator | strip bottom-left of speaker map: blank = not connected, grey = connected, red = response sent, green = command received |

## Framing

- **Command:** two ASCII hex characters + `\r\n`. Example: `37\r\n` = `33 37 0d 0a`.
  (The prose once says `\n\r`; the packet captures show `\r\n`.)
- **Response:** one or more `KEY=VALUE` fields, **each terminated by `\x00`**.
  A single TCP packet may contain many fields (e.g. `ACH1=L\x00ACH2=R\x00…`),
  and a field may in theory be split across TCP segments → parse as a stream.
- Observed latency: ~18 ms for the assignments request.
- Command codes are shown lower-case in the tables, speaker selection codes
  upper-case (`B1`…`E2`). Case sensitivity is **(unverified)** – send lower-case.

## Table 1 – IR remote key commands

Default response is `KEY=<code>`.

| # | Key | Code | Response |
|---|---|---|---|
| 1 | POWER | `11` | `KEY=11` |
| 2 | MENU | `43` | `KEY=43` |
| 3 | BACK | `59` | `PAGE=0..999` (0 = home page) |
| 4 | ENTER | `04` | `KEY=04` |
| 5 | CANCEL | `50` | `KEY=50` |
| 6 | ADJ+ | `56` | `KEY=56` |
| 7 | ADJ- | `5a` | `KEY=5a` |
| 8 | UP | `47` | `KEY=47` |
| 9 | DOWN | `4b` | `KEY=4b` |
| 10 | LEFT | `57` | `KEY=57` |
| 11 | RIGHT | `53` | `KEY=53` |
| 12 | 1 | `5d` | `KEY=5d` |
| 13 | 2 | `5f` | `KEY=5f` |
| 14 | 3 | `49` | `KEY=49` |
| 15 | 4 | `16` | `KEY=16` |
| 16 | 5 | `17` | `KEY=17` |
| 17 | 6 | `44` | `KEY=44` |
| 18 | 7 | `55` | `KEY=55` |
| 19 | 8 | `0f` | `KEY=0f` |
| 20 | 9 | `0e` | `KEY=0e` |
| 21 | 0 | `5b` | `KEY=5b` |
| 22 | * | `12` | `KEY=12` |
| 23 | # | `36` | `KEY=36` |
| 24 | CAL | `03` | `KEY=03` |
| 25 | SPK | `0b` | `KEY=0b` |
| 26 | HP | `0a` | `KEY=0a` |
| 27 | C | `1c` | `KEY=1c` |
| 28 | L | `1d` | `KEY=1d` |
| 29 | R | `46` | `KEY=46` |
| 30 | Lw | `0d` | `KEY=0d` |
| 31 | Rw | `0c` | `KEY=0c` |
| 32 | Ls | `15` | `KEY=15` |
| 33 | Rs | `45` | `KEY=45` |
| 34 | Lb | `00` | `KEY=00` |
| 35 | Rb | `1b` | `KEY=1b` |
| 36 | LFE | `4c` | `KEY=4c` |
| 37 | OH | `14` | `KEY=14` |
| 38 | ALL (toggle solo/mute) | `1a` | `ALL=SOLO` or `ALL=MUTE` |
| 39 | headphone | `4d` | `MODE=SVS` |
| 40 | speaker | `5e` | `MODE=AV` / `MODE=MIX` / `MODE=SVS` |
| 41 | A vol+ | `30` | `VA=27..99` `TRI=1..3` |
| 42 | A vol- | `31` | `VA=27..99` `TRI=1..3` |
| 43 | B vol+ | `33` | `VB=27..99` |
| 44 | B vol- | `34` | `VB=27..99` |
| 45 | MUTE A | `32` | `MUTEA=MUTE` / `MUTEA=OFF` |
| 46 | MUTE B | `35` | `MUTEB=MUTE` / `MUTEB=OFF` |
| 47 | TEST | `08` | `TEST=LOOP` / `TEST=OFF` |
| 48 | HT | `42` | `HT=ACTIVE` / `HT=OFF` |
| 49 | PA | `58` | `KEY=58` |
| 50 | PB | `54` | `KEY=54` |

Note: the intro text mentions `MODE=SOLO`/`MODE=MUTE` for the ALL key; the
table says `ALL=SOLO`/`ALL=MUTE`. Trust the table **(unverified)**.

## Table 2 – Non-IR commands

### Sources

| Code | Function | Response |
|---|---|---|
| `20` | eARC | `IN=eARC` |
| `21` | HDMI 1 | `IN=HDMI-1` |
| `22` | HDMI 2 | `IN=HDMI-2` |
| `23` | HDMI 3 | `IN=HDMI-3` |
| `24` | HDMI 4 | `IN=HDMI-4` |
| `25` | USB | `IN=USB` |
| `26` | LINE | `IN=LINE` |
| `27` | STEREO | `IN=STEREO` |
| `28` | COAXIAL | `IN=COAXIAL` |
| `29` | OPTICAL | `IN=OPTICAL` |

### Power

| Code | Function | Response |
|---|---|---|
| `2c` | Power up | `PWR=ON` |
| `2d` | Standby | `PWR=STANDBY` |
| `2e` | Power status | `PWR=ON` / `PWR=STANDBY` / `PWR=BOOT` |

### Status / info

| Code | Function | Response |
|---|---|---|
| `37` | DSP A+B speaker assignments | `ACH1=L`, `ACH2=R`, … `ACH24=…`; `BCH1=…` … `BCH16=…` |
| `38` | Reset all level meters | `L1=00` … `L24=00`, `AHL=00` … `BTR=00` |
| `64` | Firmware info | `A16FW=`, `APMFW=`, `HSRFW=`, `HTFW=`, `A16SN=` (serial) |
| `6a` | All levels | `L1..L24=00..99`, `AHL=00..99` … `BTR=00..99` |
| `80` | User A info | see below |
| `83` | User A volume | `VA=27..99` `TRI=1..3` |
| `85` | User A head-tracker angle | `AHT=string` |
| `a0` | User B info | see below |
| `a3` | User B volume | `VB=27..99` |
| `a5` | User B head-tracker angle | `BHT=string` |
| `ae` | Speaker key visibility | `V00`, `V01`, … `Vnn` (nn = speaker ID) |
| `af` | Active speaker status | `A00`, `A01`, … `Ann` |

Level meter channel keys besides `L1..L24`: `AHL`, `AHR`, `ATL`, `ATR`, `BHL`,
`BHR`, `BTL`, `BTR` (headphone / tactile L/R for user A/B; confirmed by the
meter screenshot Fig. 11, not yet seen on the device).

**User A info (`80`):**
`AUR` user name · `PA` preset no. · `VA` volume · `TRI` tri-level (1–3) ·
`AROOM` room · `ANAME` subject · `ASPKR` layout · `AQFILE` HPEQ file ·
`AQNAME` HPEQ subject · `AQTYPE` HPEQ filter type · `AQMOD` headphone model ·
`ATACT` tactile ON/OFF · `IN` source · `DEC` active decoder · `LM` listening
mode · `UMIX` upmixer · `HTMODE` head-tracker mode · `LEG` Dolby/DTS legacy ·
`USER` single/dual user mode.

**User B info (`a0`):**
`BUR` · `PB` · `VB` · `BROOM` · `BNAME` · `BSPKR` · `BQFILE` · `BQNAME` ·
`BQTYPE` · `BQMOD` · `BTACT` (no TRI and no global fields).

### Presets

| Codes | Function | Response |
|---|---|---|
| `70`–`7f` | User A preset 1–16 | `PA=01` … `PA=16` |
| `90`–`9f` | User B preset 1–16 | `PB=01` … `PB=16` |

Preset n = base + (n − 1), base `0x70` (A) / `0x90` (B).

### Speaker selection (solo / mute)

| Codes | Function | Response |
|---|---|---|
| `b1`–`e2` | Select speaker ID 1–50 (ID = code − `0xB0`) | solo mode: `A00` `Ann`; mute mode: toggles `Ann` ↔ `Mnn` |

### Speaker IDs (Table 3)

Table 3 of the PDF exists only as an image (a top view of the room with the
designator and ID in each box). The layer comes from the colours of Table 4.
Constant in code: `pya16.speakers.SPEAKERS`.

| ID | Designator | Layer | Position (our reading of the diagram) | Grid row/col | Select code |
|---|---|---|---|---|---|
| 1 | `L` | floor | front left | 0/1 | `b1` |
| 2 | `R` | floor | front right | 0/7 | `b2` |
| 3 | `C` | floor | centre | 0/4 | `b3` |
| 4 | `SW` | lfe | subwoofer, front left corner | 0/0 | `b4` |
| 5 | `Ls` | floor | left surround | 4/0 | `b5` |
| 6 | `Rs` | floor | right surround | 4/8 | `b6` |
| 7 | `Lb` | floor | left back | 6/1 | `b7` |
| 8 | `Rb` | floor | right back | 6/7 | `b8` |
| 9 | `Lss` | floor | left side surround | 3/0 | `b9` |
| 10 | `Rss` | floor | right side surround | 3/8 | `ba` |
| 11 | `Cr` | floor | centre rear | 6/4 | `bb` |
| 12 | `SW2` | lfe | subwoofer 2, front right corner | 0/8 | `bc` |
| 13 | `Lw` | floor | left wide | 1/0 | `bd` |
| 14 | `Rw` | floor | right wide | 1/8 | `be` |
| 15 | `Lbs` | floor | left back surround | 6/3 | `bf` |
| 16 | `Rbs` | floor | right back surround | 6/5 | `c0` |
| 17 | `Lc` | floor | left centre | 0/2 | `c1` |
| 18 | `Rc` | floor | right centre | 0/6 | `c2` |
| 19 | `Lu` | under | left under, front | 2/3 | `c3` |
| 20 | `Ru` | under | right under, front | 2/5 | `c4` |
| 21 | `Cu` | under | centre under | 2/4 | `c5` |
| 22 | `Ch` | height | centre height, front | 1/4 | `c6` |
| 23 | `Chr` | height | centre height, rear | 5/4 | `c7` |
| 24 | `T` | overhead | top, above the listener | 3/4 | `c8` |
| 25 | `Lh` | height | left height, front | 1/2 | `c9` |
| 26 | `Rh` | height | right height, front | 1/6 | `ca` |
| 27 | `Lhs` | height | left height side | 3/1 | `cb` |
| 28 | `Rhs` | height | right height side | 3/7 | `cc` |
| 29 | `Lhr` | height | left height rear | 5/2 | `cd` |
| 30 | `Rhr` | height | right height rear | 5/6 | `ce` |
| 31 | `Ltf` | overhead | left top front | 2/2 | `cf` |
| 32 | `Rtf` | overhead | right top front | 2/6 | `d0` |
| 33 | `Ltm` | overhead | left top middle | 3/2 | `d1` |
| 34 | `Rtm` | overhead | right top middle | 3/6 | `d2` |
| 35 | `Ltr` | overhead | left top rear | 4/2 | `d3` |
| 36 | `Rtr` | overhead | right top rear | 4/6 | `d4` |
| 37 | `Lsc` | floor | left screen centre | 0/3 | `d5` |
| 38 | `Rsc` | floor | right screen centre | 0/5 | `d6` |
| 39 | `Ls1` | floor | left surround 1 (front of Lss) | 2/0 | `d7` |
| 40 | `Rs1` | floor | right surround 1 (front of Rss) | 2/8 | `d8` |
| 41 | `Lrs1` | floor | left rear surround 1 | 5/0 | `d9` |
| 42 | `Rrs1` | floor | right rear surround 1 | 5/8 | `da` |
| 43 | `Lrs2` | floor | left rear surround 2 | 6/2 | `db` |
| 44 | `Rrs2` | floor | right rear surround 2 | 6/6 | `dc` |
| 45 | `Lhw` | height | left height wide | 1/1 | `dd` |
| 46 | `Rhw` | height | right height wide | 1/7 | `de` |
| 47 | `Lhs1` | height | left height side 1 | 4/1 | `df` |
| 48 | `Rhs1` | height | right height side 1 | 4/7 | `e0` |
| 49 | `Lbu` | under | left back under | 5/3 | `e1` |
| 50 | `Rbu` | under | right back under | 5/5 | `e2` |
| 51 | `SW` | lfe | subwoofer, rear left corner | 6/0 | — |
| 52 | `SW` | lfe | subwoofer, rear right corner | 6/8 | — |

- The designators are unique except `SW`: IDs 4, 51 and 52 are all named
  `SW` (12 is `SW2`). `BY_DESIGNATOR["SW"]` therefore maps to 4.
- Only IDs 1–50 have select commands. 51/52 appear only on the map.
- The `ACHn`/`BCHn` fields of `37` use the designators.
- `Vnn`/`Ann`/`Mnn` use the IDs; `00` is not a speaker ID.

### LCD loudspeaker map (Table 4)

Table 4 of the PDF also exists only as an image: the speaker map shown on the
A16 display. It is a grid with 7 rows × 9 columns. Row 0 is the screen side,
column 0 is left, and the listener sits in the middle (rows 3–4, cols 3–5; ID
24 `T` is above the seat). Empty cells have no speaker. Function in code:
`pya16.speakers.grid()`, rows/cols per ID in `Speaker.row`/`.col`.

Colours (layers): floor = green, height = orange, overhead = lilac,
under = yellow, LFE = red.

| row \ col | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| **0** | 4 SW | 1 L | 17 Lc | 37 Lsc | 3 C | 38 Rsc | 18 Rc | 2 R | 12 SW2 |
| **1** | 13 Lw | 45 Lhw | 25 Lh |  | 22 Ch |  | 26 Rh | 46 Rhw | 14 Rw |
| **2** | 39 Ls1 |  | 31 Ltf | 19 Lu | 21 Cu | 20 Ru | 32 Rtf |  | 40 Rs1 |
| **3** | 9 Lss | 27 Lhs | 33 Ltm |  | 24 T |  | 34 Rtm | 28 Rhs | 10 Rss |
| **4** | 5 Ls | 47 Lhs1 | 35 Ltr |  |  |  | 36 Rtr | 48 Rhs1 | 6 Rs |
| **5** | 41 Lrs1 |  | 29 Lhr | 49 Lbu | 23 Chr | 50 Rbu | 30 Rhr |  | 42 Rrs1 |
| **6** | 51 SW | 7 Lb | 43 Lrs2 | 15 Lbs | 11 Cr | 16 Rbs | 44 Rrs2 | 8 Rb | 52 SW |

The grid is checked in `tests/test_speakers.py` against a second, independent
transcription of the image.

### Centro app screenshots (Fig. 1, 10–12)

The screenshots of the manufacturer's example app add no new commands. They
confirm, however:
- Fig. 1/10 (control page): source buttons eARC, HDMI 1–4, COAX, LINE,
  OPTICAL, USB; per user preset 1–12 in the grid, volume 68 with a tri-level
  1/2/3 switch for user A only; fields Listening Room, Layout, Subject, HPEQ
  file/subject/date/type, Headphone, Tactile. Header: Audio, Upmixer, Format,
  Users, Legacy, HT mode. This matches the fields of `80`/`a0` (incl.
  `AQDATE`).
- Fig. 11 (meters): 24 channel levels per user plus `HP L`, `HP R`,
  `TACT L`, `TACT R` per user. This confirms the level keys
  `AHL AHR ATL ATR BHL BHR BTL BTR`.
- Fig. 12 (speaker map, layout 15.1.6): speaker buttons arranged like
  Table 3, plus TEST, SVS/STEREO, SOLO/ALL and volume with tri-level 1–3.
  That corresponds to the commands `b1`–`e2`, `08`, `1a`, `30`/`31`.

## Observed on a real device (FW 2.17, 2026-11-12)

Details and open points: see `CLAUDE.md` → "Beobachtungen am echten Gerät".

> **Test environment:** all measurements so far were made from a PC connected
> by **WLAN with poor quality**: ping to the A16 34–567 ms, mean 126 ms, no
> loss (30 pings). Response times below therefore include up to ~0.5 s of
> network jitter; the device's base latency is ~0.5 s (stable `PWR=STANDBY`
> answers). Dropped commands are **not** explained by the WLAN: TCP
> retransmits, and the missed keepalives never got a late answer either. The
> one connection abort (WinError 121) and one 10 s connect failure may be WLAN
> related. Repeat timing measurements from a wired host when possible.

- Every packet ends with `\x00\r`; fields may start with `\r` → strip them.
- Bare fields without `=` exist (`V00`, `A01`, …).
- The A16 pushes status unsolicited roughly every 0.9–1.4 s.
- Extra keys not in the PDF: `AQDATE`/`BQDATE`, `MODE` in the speaker block.
- `83` returns only `VA=nn` (no `TRI` unless tri-level is enabled).
- Only one client at a time: a second connect attempt times out while the
  first connection is active.
- Inactivity timeout counts client-sent data only. After it expires (~120 s on
  the test device) the A16 stops pushing and drops the connection silently
  (no FIN). The next write fails with a reset. Use a keepalive below 30 s.

### Keepalive test (2026-11-12, 6 min, `2e` every 20 s)

- **The connection stays up well past the ~120 s timeout:** pushes continued
  for the full 366 s (290 packets, largest gap 1.86 s), no reset, no EOF.
  `2e` resets the inactivity timer.
- 17 of 19 keepalives answered with `PWR=ON`, response time 0.59–1.35 s
  (median 0.71 s).
- The 2 misses had different causes:
  1. the `2e` sent immediately after connecting was ignored. The first push
     arrived only 1.6 s after the connect, so the A16 needs a moment before it
     accepts commands.
  2. one `2e` at 220 s was dropped although the connection was healthy and the
     pushes continued.

### Dropped commands

- The A16 occasionally drops a command without answering, on a healthy
  connection. Observed rate: 1 of 18 keepalives (20 s spacing) and 2–3 of 28
  queries in quick succession (0.05–0.5 s gap). With a 1 s gap 0 of 28 were
  dropped, but that sample is small and makes a refresh take ~26 s instead of
  ~15 s.
- Commands right after a (re)connect are dropped more often.
- Response times are usually 0.6–1.5 s, occasionally up to ~2.7 s (`64`).
- Consequences in `pya16`:
  - send commands only after the first packet arrives (max. 3 s)
  - retry idempotent commands (queries, power, source, preset) once
  - never retry toggles and steps blindly (volume, mute, IR keys)
  - a missed keepalive is retried once; only two misses in a row mean the
    connection is dead
  - the periodic AUR/BUR block does not confirm other commands (it also
    contains `VA`, `PA`, `IN`)

### Command rate: minimum interval (2026-11-12, `tools/a16_volume_probe.py`)

**The A16 ignores a command that arrives less than ~1 s after the previous
one.** Measured with two volume steps of user A at different send-to-send
gaps:

| gap | applied |
|---|---|
| 0.4 s | 1 of 2 |
| 0.6 s | up 2 of 2, down 1 of 2 |
| 0.8 s | 1 of 2 (both directions) |
| 1.0 s | 2 of 2 |
| 1.3 s | 2 of 2 |

- An ignored **volume step is still answered**, with the *unchanged* `VA=`.
- An ignored **mute toggle** (`32`) gets **no answer at all**.
- The answers report the current value correctly. The earlier suspicion of
  "stale duplicate `VA=`" was wrong: those were ignored steps.
- This explains many of the "dropped commands" above (fast refresh).
- `pya16` therefore keeps a **minimum send-to-send interval of 1.2 s**
  (`min_command_interval`; 1.0 s worked, plus margin for WLAN jitter). A step
  answered with an unchanged value is sent once more.

### Lost commands and late answers in Home Assistant (2026-11-12)

Running the integration in Home Assistant (WSL, same poor WLAN) with the 1.2 s
interval:
- some commands still got **no answer at all** (volume steps, `32`, `21`),
  roughly one in four or five during busy minutes, then for minutes none
- some answers arrived **3–5 s late**
- a volume query after an unanswered step always showed the old value, so
  those steps were really lost, not just their answers
- whether this comes from the WLAN path or the device cannot be separated
  from here; repeat over a wired network

Consequences in `pya16` / the integration:
- `response_timeout` default **5 s** (was 3 s)
- an unanswered volume step is followed by a volume query (`83`/`a3`):
  unchanged → the step is sent again; changed → it was applied
- a volume target keeps stepping until it is reached (64 → 66 → 64 worked
  despite three lost steps)
- there is no query for the mute state: after an unanswered toggle the mute
  state becomes **unknown** (`None`) instead of showing a possibly wrong value

### Volume steps need ~2.5 s, user B is pushed (2026-11-12, wired path)

Measured with 3 steps up and 3 down per run (Home Assistant on a wired
Raspberry Pi had been the client before; the measurement PC is on WLAN):

| gap between steps | applied |
|---|---|
| 1.5 s, user A | 2 of 6 |
| 1.5 s, user B | 4 of 6 |
| 2.5 s, user A | 6 of 6 |
| 3.0 s, user A | 6 of 6 |

- Other commands work at 1.2 s; **volume steps need about 2.5 s**. `pya16`
  uses `min_step_interval = 2.5` s for `30`/`31`/`33`/`34`.
- In Home Assistant on the wired Pi, step answers came after ~0.3 s, and
  steps at 1.2 s were also ignored (diagnosed from the HA log).

**User B is pushed when it is operated with the remote:** after each volume
step `VB=nn` arrives at once and the complete user B block (`BUR … BSPKR`)
about 1 s later. After a preset change the B block arrives with the new
`PB`, `BROOM` and `BNAME`. The answer to the select command itself (`90`–`9f`)
is only `PB=nn`, so the integration queries `a0` after its own preset change.

### Connecting shortly after another client disconnected

- After a client disconnected (e.g. Home Assistant stopped, a capture tool
  ended, or a bare TCP connect/close without data), the A16 often **refused
  new connections for ~30–60 s**. Observed: connect timeouts (33 s and 55 s
  until success), or accept and **reset within 60–80 ms**.
- Not every time: three CLI sessions in a row 1.5 s apart all worked.
- `pya16` reports "connected" only when the A16 is ready (first packet or
  `ready_timeout`), so such immediate resets do not make entities flap. The
  reconnect backoff handles the rest. The config flow error text tells the
  user to wait about a minute.

### Speaker table check against the device (2026-11-12)

Spot check of Table 3 against the device (user A, layout `12.1.10`):
- `37` listed 16 designators: `ACH1…ACH16` = L R C SW Lss Rss Lb Rb Lw Rw Lh
  Rh Ltf Rtf Ltm Rtm. All of them are in Table 3.
- Mapped via Table 3 they give IDs 1 2 3 4 7 8 9 10 13 14 25 26 31 32 33 34.
- `ae` (visible, without `00`) and `af` (active, without `00`) returned
  **exactly the same 16 IDs**. No speaker was muted.
- The older capture with layout `7.1.6a` is consistent too: the visible
  heights were 22 24 25 26 27 28 = Ch T Lh Rh Lhs Rhs.

`ae` and `af` each answered with one packet. The answer to `af` also contains
`ALL=…`, `TEST=…` and **`MODE=…`**, so `af` is the way to query the mode
(SVS/AV/MIX). `pya16` includes `af` in `refresh()`.

### Standby and power on (2026-11-12, `tools/a16_standby_test.py`)

**Standby (`2d`):**
- answered with `PWR=STANDBY` after ~0.65 s
- in standby the connection stays up
- `2e` keepalives are answered reliably with `PWR=STANDBY` (6/6, ~0.5 s)
- there are **no pushes at all** in standby: only the answers to `2e`

**Power on (`2c`) from standby:**

| after `2c` | event |
|---|---|
| 0.5 s | `PWR=BOOT` |
| 0.5–60 s | the A16 answers **nothing**; all keepalives unanswered |
| ~60.7 s | the A16 **resets the TCP connection** (next read fails with a reset) |
| 61.7 s | reconnect; `2e` answered immediately with `PWR=ON` (~0.7 s) |
| ~65 s | first user A block (3.7 s after the reconnect) |

**After the boot** the push behaviour was different from before:
- no periodic ~1 s pushes; a user A block came only ~5 s after each command
- that block started with a **corrupted first field** (`" 1"` instead of
  `"AUR=User 1"`), so it must not be identified by `AUR` alone
- `pya16` therefore treats a packet with `AUR`/`BUR`/`AROOM`/`BROOM` as an
  info block, which does not confirm other commands

Why the periodic pushes happen at some times and not at others is unknown
(maybe linked to the display/menu state or head tracking). Clients must not
rely on them.

**Consequences in `pya16`:** while the state is `PWR=BOOT`, unanswered
keepalives do not end the connection; the device's own reset ends it. A
`boot_timeout` (120 s) is the safety net. The reconnect follows after 1 s,
because the previous connection was healthy.

## Known open questions

- Does the push behaviour change with *TCP slave response* disabled?
- What triggers the periodic ~1 s pushes, and why were they missing after
  the boot?
- What happens on `2c` while already on, and on `2d` during the boot?
- Upper/lower case handling of command codes.
