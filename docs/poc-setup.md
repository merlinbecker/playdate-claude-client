# POC auf dem lokalen Rechner

Ziel: Playdate und Server im selben WLAN, Ablauf „sprechen → Karte“ ausprobieren, bevor eine VM nötig ist.

## 1. Server

Voraussetzungen: Python 3.11+, für den echten Agenten Node.js und Claude Code (`claude` eingeloggt).

```bash
cd server
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Token setzen
set -a; . ./.env; set +a
uvicorn main:app --host 0.0.0.0 --port 8000
```

Beim ersten Transkribieren lädt faster-whisper das Modell herunter (`small` ca. 500 MB).

## 2. Ohne Playdate testen

```bash
python3 tools/fake_playdate.py --token <TOKEN> --text "Hallo"
python3 tools/fake_playdate.py --token <TOKEN> --wav meine-aufnahme.wav --drop-after 2
python3 tools/fake_playdate.py --token <TOKEN> --choose again
```

`--drop-after` simuliert einen Verbindungsabbruch; der Upload muss danach fortgesetzt werden.

## 3. Echter Agent

```bash
mkdir -p ~/assistant   # Arbeitsverzeichnis, gern mit eigener CLAUDE.md
PDC_AGENT=claude PDC_AGENT_DIR=~/assistant uvicorn main:app --host 0.0.0.0 --port 8000
```

Der Worker merkt sich die Session-ID und setzt sie mit `--resume` fort. Für eine frische Session den Eintrag `session` in der Tabelle `state` löschen.

Berechtigungen des Agenten über `~/assistant/.claude/settings.json` einschränken.

## 4. Playdate

1. `playdate/source/config.example.lua` nach `config.lua` kopieren, IP des Rechners und Token eintragen.
2. Bauen: `pdc playdate/source build/ClaudeClient.pdx`
3. Im Simulator testen, dann per Sideload auf das Gerät.
4. Beim ersten Start fragt der Playdate, ob die App den Server kontaktieren darf.

Bedienung: A halten = sprechen, A tippen = Auswahl bestätigen, ◀ ▶ = Karten, ▲ ▼ = Auswahl, Kurbel = scrollen.

## 5. Auf Hardware prüfen

- [ ] Liefert `sample:save("….wav")` einen 44-Byte-Header? Sonst Offset in `recorder.lua` anpassen.
- [ ] 8-Bit-WAV unsigned oder signed? Bei verrauschtem Ergebnis `Config.signed = true`.
- [ ] Funktioniert `conn:query("PUT", …)` mit Binärdaten? Sonst Chunks per `POST` und Server-Route ergänzen.
- [ ] Wie lange dauert das Downsampling von 10 s Audio?
- [ ] Zeit vom Loslassen bis zur ersten Karte messen.
