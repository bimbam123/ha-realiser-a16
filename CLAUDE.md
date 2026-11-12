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
   exponentiellem Backoff. Keepalive (z. B. `2e`) in einem Intervall unter
   dem kleinsten Inaktivitäts-Timeout des A16 (30 s).
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

## Architektur

- `custom_components/realiser_a16/api.py`: reiner asyncio-Protokoll-Client
  **ohne HA-Imports** (Parser, Verbindung, Queue, Callbacks).
- `coordinator.py`: verbindet den Client mit HA (Push-Updates, Verfügbarkeit).
- Eine Plattformdatei pro Entitätstyp mit `has_entity_name = True`,
  `DeviceInfo` aus Seriennummer (`A16SN`) und Firmware (`A16FW`).
- `unique_id` des Config-Entries ist die Seriennummer.

## Arbeitsweise

- Kleine, überprüfbare Schritte. Vor größeren Änderungen einen Plan zeigen.
- **Commits und Pushes nur nach Rückfrage.**
- Tests: `pytest` für `api.py` gegen einen Fake-TCP-Server (asyncio). Den
  Parser mit fragmentierten Paketen testen.
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
