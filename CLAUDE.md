# CLAUDE.md – ha-realiser-a16

## Ziel

Inoffizielle Home-Assistant-Custom-Integration (`realiser_a16`) für den
**Smyth Realiser A16**. Sie steuert das Gerät über dessen TCP-Command-Server
(Firmware ≥ 1.90). Die Integration wird über den **Home Assistant Marketplace**
verteilt (in HA eingebaut seit 2026.11, Nachfolger von HACS) und soll in den
Standardkatalog (hacs/default) aufgenommen werden.

Geplante Entitäten:

- `media_player`: Power on/standby, Quellenwahl
- `number` oder Lautstärke im media_player: Lautstärke A/B (27–99)
- `select`: Presets A/B (1–16)
- `switch`: Mute A/B
- `sensor`: Firmware, Raum, Layout, Decoder, Upmixer, HT-Modus, HT-Winkel
- `button`: IR-Tasten (Menü, Pfeile, ENTER, BACK …)

## Protokollregeln (verbindlich)

Maßgeblich ist [`docs/protocol.md`](docs/protocol.md). Die Hersteller-PDF
bleibt lokal und wird **nie** committet. Sie wird auch **nie komplett
gelesen** (~25k Tokens): zuerst `docs/protocol.md` nutzen, bei Bedarf nur
einzelne Seiten der PDF lesen (`pages`).

1. **Befehl** = 2 ASCII-Hexzeichen + `\r\n`, klein geschrieben (`"6a\r\n"`).
2. **Antwort** = Felder `KEY=VALUE`, jedes mit `\x00` abgeschlossen. Den
   Datenstrom puffern, an `\x00` trennen und erst danach am ersten `=`
   aufteilen. Ein TCP-Paket kann beliebig viele Felder enthalten, ein Feld
   kann über mehrere Pakete verteilt sein.
3. **Keine Request/Response-Zuordnung.** Jedes empfangene Feld wird in einen
   zentralen State übernommen. Der A16 schickt mit „TCP slave response“ auch
   unaufgefordert Felder.
4. **Genau eine persistente Verbindung** pro Gerät. Reconnect mit
   exponentiellem Backoff. Keepalive `2e` alle 20 s. Ein verpasster Keepalive
   wird sofort wiederholt, erst zwei Fehlschläge hintereinander bedeuten eine
   tote Verbindung. (Der A16 verschluckt gelegentlich einzelne Befehle, siehe
   `docs/protocol.md` → „Dropped commands“.)
4a. Erst senden, wenn nach dem Verbinden das erste Paket angekommen ist.
   Idempotente Befehle einmal wiederholen, Toggles und Schritte (Lautstärke,
   Mute, IR-Tasten) **nie** automatisch wiederholen.
5. Befehle werden über eine Queue **nacheinander** gesendet, mit kurzem Abstand
   und ohne Flooding.
6. Wertebereiche einhalten: Lautstärke 27–99, Presets 1–16, Speaker-ID 1–50,
   Port 512–65535.
7. `PWR=BOOT` ist ein eigener Zustand (Gerät fährt hoch). Er bedeutet nicht
   „an“.
8. Unbekannte Keys loggen (debug) und ignorieren, niemals abstürzen.
9. Was in `docs/protocol.md` als *(unverified)* markiert ist, darf nicht als
   gesichert behandelt werden. Neue Erkenntnisse vom echten Gerät kommen dort
   hinein.

## Beobachtungen am echten Gerät

Test am 2026-11-12, A16 unter 192.168.1.5:4101, FW `A16FW=2.17 Jan 26 2024`,
Tool `tools/a16_capture.py`, Rohdaten in `docs/captures/`. Die Captures
enthalten Seriennummer und Presetnamen. Vor einem Commit prüfen, ob sie
öffentlich sein sollen.

Zwei Läufe. In Lauf 1 (`…-132359-…`) wurde das Gerät parallel von Hand
bedient. Lauf 2 (`…-133219-…`) lief ohne Bedienung und ist die Referenz.

**Framing**
- **Jedes Paket endet mit `\x00\r`.** Hängen Pakete im Stream aneinander,
  beginnt das nächste Feld mit `\r` (z. B. `"\rVA=54"`). Felder deshalb
  trimmen (`strip()`).
- **Es gibt Felder ohne `=`**, z. B. `V00 V01 … A00 A01 …` als
  Lautsprecher-Sichtbarkeit und -Status. Der Parser behält sie
  (`Field.value is None`).
- **Leere Felder** (`\x00\x00`) kommen vor, z. B. in der Antwort auf `64`.

**Pushes**
- **Nicht auf periodische Pushes verlassen.** Im Standby gibt es gar keine,
  und nach einem Boot kamen sie nur noch ~5 s nach jedem Befehl. Außerdem
  fehlte dem User-A-Block dann das `AUR=` (siehe `docs/protocol.md` →
  „Standby and power on“).
- **Einschalten aus dem Standby dauert ~65 s:** `PWR=BOOT`, dann ~60 s keine
  Antworten, danach trennt der A16 die TCP-Verbindung selbst.
- In den ersten Läufen pushte der A16 ohne Anfrage laufend Status, etwa alle 0,9–1,4 s, den
  kompletten User-A-Block (`AUR … USER`). Das beginnt schon direkt nach dem
  Verbinden.
- Bei Bedienung von Hand kommen sofort Einzelfelder (`VA=56`) und
  gelegentlich der Block `V…/A… ALL= TEST= MODE=`. `local_push` ist damit
  bestätigt.
- Antworten stecken mitten im Push-Strom. Regel 3 (keine Zuordnung von
  Antwort zu Befehl) ist zwingend.

**Antworten (Lauf 2, Verzögerung nach dem Senden)**
- `2e` → `PWR=ON` (~0,6 s)
- `64` → `A16FW`, `APMFW`, `HSRFW`, `HTFW`, `A16SN` (~0,7 s)
- `80` → User-A-Block, nicht vom normalen Push zu unterscheiden
- `83` → nur `VA=64`, **ohne `TRI`** (laut PDF kommt `TRI` nur bei
  aktivem Tri-Level)
- `a0` → `BUR … BTACT`, inkl. `BQDATE` (~0,6 s)
- `37` → `ACH1…ACH24`, `BCH1…BCH16`, nicht belegte Kanäle leer (`ACH17=`)
  (~0,7 s)
- Zusätzliche Keys, die das PDF nicht nennt: `AQDATE`/`BQDATE` (HPEQ-Datum)
  und `MODE=SVS` im Speaker-Block.

**Verbindungen**
- **Nur ein Client gleichzeitig.** Solange c1 aktiv ist, läuft der Aufbau
  einer zweiten Verbindung nach 5 s in einen Timeout. c1 arbeitet dabei
  ungestört weiter. (In Lauf 1 wurde c2 angenommen, vermutlich weil c1 dort
  schon still abgebaut war.)
  → Die Integration darf **keine** zweite Verbindung öffnen. Eine andere
  Steuer-App blockiert die Integration und umgekehrt.

**Inaktivitäts-Timeout**
- Er zählt nur, was der **Client** sendet. Die eigenen Pushes des A16 halten
  die Verbindung nicht offen.
- Etwa **120 s nach dem letzten gesendeten Befehl** hört der A16 auf zu
  pushen und baut die Verbindung **still** ab, ohne FIN/EOF beim Client.
  Erst der nächste Schreibversuch scheitert mit `ConnectionResetError`.
  Danach ist ein Reconnect sofort möglich (~60 ms).
  (Der Timeout am Gerät steht vermutlich auf 120 s, einstellbar sind
  30–250 s.)
- → **Keepalive** (`2e`) deutlich unter 30 s senden, damit jede
  Timeout-Einstellung abgedeckt ist. Bestätigt: Mit `2e` alle 20 s blieb die
  Verbindung 6 Minuten lang stabil (Details in `docs/protocol.md`).
- → Tote Verbindungen erkennt der Keepalive (kein `PWR=` auch nach einer
  Wiederholung). Auf EOF zu warten reicht nicht.

## Befehle

- Testumgebung: `python -m venv .venv`, dann
  `.venv/Scripts/python -m pip install -r requirements_test.txt`.
- Tests: `.venv/Scripts/python -m pytest -q`. Die Tests importieren `pya16`
  direkt (siehe `tests/conftest.py`), Home Assistant ist nicht nötig.
- Am Gerät ausprobieren: `python tools/a16_cli.py <host> state | monitor |
  send <code> | …`. Dabei bitte keine andere Steuer-App verbinden, denn der
  A16 nimmt nur einen Client an.
- Neue Mitschnitte: `tools/a16_capture.py`. Vor einer Übernahme als
  Testdaten mit `tools/anonymize_capture.py` anonymisieren.

## Architektur

- `custom_components/realiser_a16/pya16/`: Protokoll-Bibliothek **ohne
  HA-Imports**, nur stdlib und relative Imports (später als PyPI-Paket
  auslagerbar). Sie besteht aus `protocol.py` (Codes, erwartete
  Antwort-Keys), `parser.py` (Stream → Pakete), `state.py` (`A16State`) und
  `client.py` (`A16Client`: eine Verbindung, Queue, Keepalive, Reconnect).
- `api.py`: dünne Schicht für HA (z. B. Geräteprüfung im Config Flow).
- `coordinator.py`: verbindet den Client mit HA (Push-Updates, Verfügbarkeit).
- Eine Plattformdatei pro Entitätstyp mit `has_entity_name = True`,
  `DeviceInfo` aus Seriennummer (`A16SN`) und Firmware (`A16FW`).
- `unique_id` des Config-Entries ist die Seriennummer.

## Arbeitsweise

- Kleine, überprüfbare Schritte. Vor größeren Änderungen einen Plan zeigen.
- **Commits und Pushes nur nach Rückfrage.**
- Tests: `pytest` für `pya16` mit den Fixtures und einem nachgebauten A16
  (`tests/conftest.py`). Neue Protokollfälle immer mit Test abdecken.
- Lint und Format: `ruff check` und `ruff format`.
- CI (muss grün sein): `hassfest` und `hacs/action` (Marketplace-Validierung).
  Checks nie per `ignore` abschalten, sonst ist der Katalog ausgeschlossen.
- Marketplace-Regeln:
  - `version` in `manifest.json` = Release-Tag (SemVer, z. B. `v0.2.0` ↔ `0.2.0`).
  - Übersetzungen nur in `translations/` (vollständiges `en.json`, dazu
    `de.json`). Custom Integrations bekommen kein `strings.json`.
  - Icons in `custom_components/realiser_a16/brand/`. Weder HA- noch
    Smyth-Logos verwenden.
  - Alles, was die Integration braucht, liegt im Integrationsordner.
- Keine neuen Abhängigkeiten in `requirements` ohne guten Grund. Das Protokoll
  braucht nur die stdlib.
- README bleibt englisch und behält den Hinweis „unofficial, not affiliated
  with Smyth Research“.
