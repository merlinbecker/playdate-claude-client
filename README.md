# playdate-claude-client

Sprich mit deinem eigenen, dauerhaft laufenden Claude-Code-Agenten – vom Playdate aus.

Der Playdate nimmt Sprache auf (auch offline, auf dem Gerät gepuffert), lädt sie bei WLAN-Verbindung in wiederaufnehmbaren Häppchen hoch. Ein selbst gehosteter Server transkribiert (lokal mit Whisper oder optional über die Voxtral-API) und gibt den Auftrag an einen langlebigen Claude-Agenten. Der Agent antwortet mit kleinen, deklarativ beschriebenen 1-Bit-Karten (Text, Icons, Tilesets, Animationen, Auswahl), die der Playdate rendert.

```
Playdate ──(Audio-Chunks, PUT)──▶ Server: Ingest → Transkription → Queue → Agent (Claude Code)
   ▲                                                                  │
   └──────────────(Karten, GET /inbox)────────────────────────────────┘
```

## Vision

Der Playdate-Client ist der erste Baustein von **Arborist**: einem persönlichen Assistenten, der als Claude Code 24/7 auf einer VM läuft. Er wird von mehreren registrierten Geräten bedient (Playdate, Web-UI mit Dashboard und Terminal, Handy), verteilt Aufgaben an Projekt-Subagenten und bekommt externe Tools nur über einen Rechte- und Tool-Broker. Ein Lagebild-Subagent liefert Cheat Sheets und vorgefertigte nächste Schritte, damit sich alles auch ohne Sprache bedienen lässt. Details in [`docs/vision.md`](docs/vision.md).

## Status

Proof of Concept. Ziel des POC: flüssiger Ablauf von „A drücken und sprechen“ bis „Karte erscheint“ mit einem Agenten, der einfach antwortet.

## Struktur

| Pfad | Inhalt |
| --- | --- |
| `docs/vision.md` | Vision und Scope von Arborist |
| `docs/arc42.md` | Architektur nach arc42 |
| `docs/karten-dsl.md` | Format der Karten, die der Agent erzeugt |
| `docs/poc-setup.md` | POC auf dem lokalen Rechner aufsetzen |
| `server/` | Ingest-API, Transkription, Queue, Agent-Worker |
| `playdate/` | Playdate-Client (Lua) |
| `tools/fake_playdate.py` | Simuliert den Playdate vom Rechner aus |

## Schnellstart (lokal)

```bash
cd server
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
PDC_TOKEN=geheim PDC_AGENT=echo uvicorn main:app --host 0.0.0.0 --port 8000
```

Dann `python3 tools/fake_playdate.py --text "Hallo"` – Details in `docs/poc-setup.md`.

## Grenzen

- Der Playdate kann nur bei geöffneter App senden und empfangen.
- Private Inhalte (Agent-Prompts, Daten, Tokens) gehören nicht ins Repo, sondern in `server/.env` bzw. das Arbeitsverzeichnis des Agenten.
