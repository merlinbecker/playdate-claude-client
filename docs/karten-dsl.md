# Karten-DSL (Version 1)

Der Agent beschreibt jede Antwort als kleine Szene in JSON. Der Playdate rendert sie mit einem generischen Renderer. Unbekannte Elementtypen werden übersprungen, damit ältere Clients nicht abstürzen.

## Aufbau einer Karte

```json
{
  "v": 1,
  "title": "Build fertig",
  "kind": "result",
  "tileset": "std",
  "elements": [
    {"t": "icon", "tile": 3},
    {"t": "text", "s": "*Tests: 12/12*"},
    {"t": "bar", "value": 0.8, "label": "Coverage"},
    {"t": "list", "items": ["demo-seite online", "3 Dateien geändert"]}
  ],
  "choices": [
    {"label": "Deployen", "value": "deploy"},
    {"label": "Später", "value": "later"}
  ]
}
```

Der Server ergänzt `id`, `job` und `ts`.

## Felder

| Feld | Pflicht | Bedeutung |
| --- | --- | --- |
| `v` | ja | Version, aktuell `1` |
| `title` | ja | Max. 30 Zeichen |
| `kind` | nein | `status`, `result`, `question`, `error` – steuert das Icon im Kopf |
| `tileset` | nein | Name oder Hash eines Tilesets, Standard `std` |
| `elements` | ja | Liste von Elementen, von oben nach unten gesetzt |
| `choices` | nein | Max. 4 Auswahlmöglichkeiten |

## Elementtypen

| `t` | Felder | Darstellung |
| --- | --- | --- |
| `text` | `s` | Textzeile, `*fett*` und `_kursiv_` wie im Playdate-Textsystem |
| `list` | `items` | Aufzählung, max. 6 Einträge |
| `icon` | `tile` | Ein 16×16-Tile aus dem Tileset |
| `bar` | `value` (0–1), `label` | Fortschrittsbalken |
| `kv` | `k`, `val` | Schlüssel links, Wert rechts |
| `sep` | – | Trennlinie |
| `image` | `hash`, `w`, `h` | 1-Bit-Bitmap aus dem Asset-Service (ab V2) |
| `anim` | `tiles`, `fps` | Tile-Folge als Animation (ab V2) |

Ohne `x`/`y` setzt der Renderer die Elemente untereinander. Mit `x`/`y` positioniert er absolut.

## Regeln für den Agenten

- Eine Kernaussage pro Karte.
- Max. sechs Zeilen à 40 Zeichen.
- Details als Folgekarte statt Textwand.
- Fragen immer mit `choices`, damit der Nutzer ohne Sprechen antworten kann.

## Standard-Tileset `std`

| Tile | Bedeutung |
| --- | --- |
| 1 | Info |
| 2 | Häkchen |
| 3 | Fehler |
| 4 | Uhr / läuft |
| 5 | Datei |
| 6 | Git |
| 7 | Globus / Web |
| 8 | Frage |

Im POC zeichnet der Client diese Icons mit Grafikprimitiven, ein echtes Tileset-Bild folgt später.
