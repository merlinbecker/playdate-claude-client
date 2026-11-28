# CLAUDE.md

## Projekt
Voice-Thin-Client für einen selbst gehosteten Claude-Code-Agenten. Playdate = dünner Client (Aufnahme, Puffer, Upload, Rendern). Alle Logik liegt auf dem Server. Architektur: `docs/arc42.md`, Zielvision: `docs/vision.md`.

## Sprache
Doku, Kommentare und Commit-Messages auf Deutsch. Bezeichner im Code auf Englisch.

## Prinzipien
- Client so dumm wie möglich: Neue Darstellungen kommen über die Karten-DSL (`docs/karten-dsl.md`), nicht über Client-Updates.
- Spracherkennung als austauschbarer Provider: lokal (faster-whisper/whisper.cpp, Standard) oder Voxtral-API. Audio geht nur an Drittanbieter, wenn die Instanz das explizit konfiguriert.
- Store-and-forward: Jede Aufnahme hat eine ID, wird in nummerierten Chunks idempotent hochgeladen und kann nach Abbruch fortgesetzt werden.
- Asynchron: Upload, Transkription und Agent sind über eine Queue entkoppelt.
- Agent-Ausgaben immer validieren. Kaputtes JSON wird zur Textkarte, nie zum Absturz.
- Generisch bleiben: Keine persönlichen Daten, Hostnamen oder Tokens ins Repo. Konfiguration über Umgebungsvariablen.

## Server
- Python 3.11+, FastAPI, SQLite. Start: `uvicorn main:app` in `server/`.
- `PDC_AGENT=echo` für Tests ohne Claude, `PDC_AGENT=claude` für den echten Agenten.
- Tests: `python3 tools/fake_playdate.py` gegen einen laufenden Server.

## Playdate
- SDK 2.x, Lua. Netzwerk-API und Mikrofon-API gegen die aktuelle SDK-Doku prüfen, bevor etwas als „funktioniert“ gilt.
- Auf echter Hardware testen: Netzwerk und Mikrofon verhalten sich im Simulator anders.
- Rechenintensives (Downsampling, ADPCM) später in C auslagern.

## Bekannte Risiken
Siehe `docs/arc42.md`, Kapitel 11.
