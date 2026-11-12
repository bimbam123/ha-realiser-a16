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
`BHR`, `BTL`, `BTR` (headphone / tactile L/R for user A/B) **(inferred from the
meter screen, unverified)**.

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

| ID | Name | ID | Name | ID | Name | ID | Name |
|---|---|---|---|---|---|---|---|
| 1 | L | 14 | Rw | 27 | Lhs | 40 | Rs1 |
| 2 | R | 15 | Lbs | 28 | Rhs | 41 | Lrs1 |
| 3 | C | 16 | Rbs | 29 | Lhr | 42 | Rrs1 |
| 4 | SW | 17 | Lc | 30 | Rhr | 43 | Lrs2 |
| 5 | Ls | 18 | Rc | 31 | Ltf | 44 | Rrs2 |
| 6 | Rs | 19 | Lu | 32 | Rtf | 45 | Lhw |
| 7 | Lb | 20 | Ru | 33 | Ltm | 46 | Rhw |
| 8 | Rb | 21 | Cu | 34 | Rtm | 47 | Lhs1 |
| 9 | Lss | 22 | Ch | 35 | Ltr | 48 | Rhs1 |
| 10 | Rss | 23 | Chr | 36 | Rtr | 49 | Lbu |
| 11 | Cr | 24 | T | 37 | Lsc | 50 | Rbu |
| 12 | SW2 | 25 | Lh | 38 | Rsc | 51 | SW (rear-left, LFE) |
| 13 | Lw | 26 | Rh | 39 | Ls1 | 52 | SW (rear-right, LFE) |

IDs 51/52 are LFE positions on the map; only IDs 1–50 have select commands.

## Observed on a real device (FW 2.17, 2026-11-12)

Details and open points: see `CLAUDE.md` → "Beobachtungen am echten Gerät".

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
  - never retry toggles and steps (volume, mute, IR keys)
  - a missed keepalive is retried once; only two misses in a row mean the
    connection is dead
  - the periodic AUR/BUR block does not confirm other commands (it also
    contains `VA`, `PA`, `IN`)

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
