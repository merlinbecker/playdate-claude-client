# Architektur nach arc42

> Dieses Dokument beschreibt den Playdate-POC. Vision und Gesamtscope von Arborist (Main-Agent, Subagenten, Device-Gateway, Rechte- und Tool-Broker) stehen in [`vision.md`](vision.md).

## 1. Einführung und Ziele

Ein dauerhaft erreichbarer persönlicher Assistent auf Basis von Claude Code, bedient per Sprache vom Playdate. Der Playdate funktioniert auch offline: Aufnahmen werden gepuffert und bei Verbindung häppchenweise hochgeladen. Ergebnisse kommen als dynamische 1-Bit-Karten mit Animation und Interaktion zurück.

| Priorität | Qualitätsziel | Messbar als |
| --- | --- | --- |
| 1 | Flüssiger Ablauf | Aufnahme startet < 200 ms nach A; Statuskarte „verstanden“ < 10 s nach Upload-Ende |
| 2 | Offline-Robustheit | Keine Aufnahme geht verloren; Upload setzt nach Abbruch fort |
| 3 | Datenschutz | Transkriptions-Provider ist pro Instanz wählbar; Standard ist lokal |
| 4 | Erweiterbare Darstellung | Neue Kartentypen ohne Client-Update |

Stakeholder: Betreiber des eigenen Servers, der zugleich einziger Nutzer ist.

## 2. Randbedingungen

- Playdate: 400×240 Pixel, 1 Bit, WLAN 2,4 GHz, Mikrofon mit 44,1 kHz, Lua- und C-API (SDK 2.x).
- Netzwerk nur bei geöffneter App; der Nutzer muss den Serverzugriff einmal erlauben.
- Keine eingebaute Audiokompression. Downsampling wird selbst implementiert.
- Claude Code im Headless-Modus (`claude -p`) oder über das Agent SDK.
- POC auf lokalem Rechner im LAN, Variante 2 auf einer Linux-VM mit HTTPS.

## 3. Kontextabgrenzung

Systemkontext von Arborist (C4, Ebene 1):

```mermaid
C4Context
    title Systemkontext Arborist

    Person(user, "Nutzer", "Lädt Ideen und Aufgaben per Sprache, Text oder Auswahl ab")

    System(arborist, "Arborist", "Persönlicher 24/7-Assistent auf Basis von Claude Code")

    System_Ext(anthropic, "Anthropic", "Claude-Modelle über das Abo des Nutzers")
    System_Ext(voxtral, "Mistral Voxtral", "Transkription per API, optional")
    System_Ext(git, "Git-Hosting", "Repos, die der Agent bearbeitet")
    System_Ext(tools, "Externe Dienste", "MCP-Server und APIs, z. B. To-do-Dienst")

    Rel(user, arborist, "Sprache, Text, Auswahl", "Playdate, Web-UI, Handy")
    Rel(arborist, user, "Karten, Lagebild, Benachrichtigungen")
    Rel(arborist, anthropic, "Prompts und Antworten", "HTTPS")
    Rel(arborist, voxtral, "Audio", "HTTPS, optional")
    Rel(arborist, git, "Commits, Pull Requests", "über den Broker")
    Rel(arborist, tools, "Tool-Aufrufe", "über den Broker")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

Für den POC relevant:

| Nachbar | Richtung | Inhalt |
| --- | --- | --- |
| Playdate | → Server | Audio-Chunks, Interaktionen (Auswahl) |
| Playdate | ← Server | Karten, Tilesets, Bitmaps |
| Anthropic | ↔ | Prompts und Antworten von Claude Code |
| Git-Hosting (z. B. GitHub) | ↔ | Repos, die der Agent bearbeitet |
| Optional: Webhosting | ← | Kleine Seiten, die der Agent veröffentlicht |

## 4. Lösungsstrategie

- **Thin Client:** Der Playdate nimmt auf, puffert, lädt hoch und rendert. Sonst nichts.
- **Store-and-forward:** Jede Aufnahme bekommt eine ID und wird in nummerierten Chunks übertragen – idempotent und wiederaufnehmbar.
- **Asynchron über eine Queue:** Upload, Transkription und Agent laufen entkoppelt.
- **Persistenter Agent:** Ein Worker führt eine fortgesetzte Claude-Code-Session (`--resume`), damit der Agent Kontext über Aufträge hinweg behält.
- **Deklarative Karten-DSL:** Der Agent beschreibt Karten als JSON-Szenen, der Client hat einen generischen Renderer.
- **Pull statt Push:** Der Playdate fragt bei geöffneter App die Inbox mit einem `since`-Cursor ab.

## 5. Bausteinsicht

### Zielbild Arborist (C4, Ebene 2)

```mermaid
C4Container
    title Container von Arborist

    Person(user, "Nutzer")

    System_Boundary(devices, "Geräte") {
        Container(pd, "Playdate-Client", "Lua, SDK 2.x", "Aufnahme, Outbox, Inbox, Karten-Renderer")
        Container(web, "Web-UI", "Browser, auch mobil", "Dashboard, Lagebild, Terminal")
    }

    System_Boundary(vm, "Azure-VM") {
        Container(gw, "Device-Gateway", "Python, FastAPI", "Registry, Ingest, Push, Ausgabe-Adapter")
        ContainerDb(q, "Eingangs-Queue", "SQLite", "Einträge mit Zustand und Verlauf")
        Container(intake, "Intake-Agent", "Python", "Transkription und Aufbereitung")
        Container(ar, "Arborist", "Claude Code CLI", "Main-Agent mit Projekt- und Lagebild-Subagenten")
        Container(br, "Rechte- und Tool-Broker", "MCP-Server", "Tokens, Rechte, Protokoll")
        Container(sched, "Scheduler", "systemd-Timer oder Cron", "Nachtwartung, Wiedervorlagen")
    }

    System_Ext(anthropic, "Anthropic")
    System_Ext(tools, "Externe Dienste")

    Rel(user, pd, "spricht, wählt aus")
    Rel(user, web, "spricht, tippt, liest")
    Rel(pd, gw, "Chunks hoch, Inbox abholen", "HTTPS, Pull")
    Rel(web, gw, "Eingaben, Push", "HTTPS, WebSocket")
    Rel(gw, q, "legt Eingaben ab")
    Rel(intake, q, "liest roh, schreibt vorbereitet")
    Rel(ar, q, "holt Batches")
    Rel(ar, gw, "Karten und Lagebild")
    Rel(ar, br, "Tool-Aufrufe", "MCP")
    Rel(br, tools, "mit gespeicherten Tokens")
    Rel(ar, anthropic, "Modellaufrufe", "HTTPS")
    Rel(sched, ar, "startet Wartung")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="2")
```

### Zustände eines Queue-Eintrags

```mermaid
stateDiagram-v2
    [*] --> received: Gerät liefert
    received --> transcribed: Audio transkribiert
    received --> prepared: Text-Eingabe
    transcribed --> prepared: Intake-Agent bereitet auf
    prepared --> queued
    queued --> in_progress: Arborist holt Batch
    in_progress --> done
    in_progress --> parked: Rückfrage, Bestätigung oder Quota leer
    parked --> queued: Antwort da oder Quota-Reset
    in_progress --> error
    error --> queued: erneuter Versuch
    done --> [*]
```

### POC-Bausteine

#### Playdate-Client

| Baustein | Aufgabe |
| --- | --- |
| Recorder | Mikrofon → Sample → WAV; Downsampling auf ca. 8,8 kHz / 8 Bit |
| Outbox | Offene Aufnahmen und Interaktionen; Chunking, Retry mit Backoff, Fortschritt |
| Inbox | Polling `/inbox?since=`, lokaler Karten-Cache für Offline-Ansicht |
| Renderer | Interpretiert die Karten-DSL |
| Asset-Cache | Tilesets und Bitmaps nach Hash |
| Input | A = sprechen/auswählen, Kurbel = scrollen, Steuerkreuz = Auswahl |

#### Server

| Baustein | Aufgabe |
| --- | --- |
| Ingest-API | `PUT /rec/{id}/chunk/{n}`, `GET /rec/{id}`, `POST /rec/{id}/done` |
| Transkription | Provider wählbar: faster-whisper/whisper.cpp lokal (Standard) oder Voxtral-API, Sprache `de` |
| Queue | SQLite-Tabelle `jobs` mit Zuständen `uploading → transcribing → queued → running → done/error` |
| Agent-Worker | Ein Thread, arbeitet Jobs nacheinander ab, hält die Session-ID |
| Card-Service | Validiert Karten, Fallback auf Textkarte, schreibt in die Inbox |
| Asset-Service | `GET /assets/{hash}` |
| Interaction-API | `POST /interaction` → neuer Job in derselben Agent-Session |

## 6. Laufzeitsicht

### Szenario A: Sprechen ohne Netz

```mermaid
sequenceDiagram
    actor N as Nutzer
    participant R as Recorder
    participant O as Outbox
    N->>R: A halten
    R->>R: in Sample aufnehmen
    N->>R: A loslassen
    R->>R: WAV speichern, auf 8,8 kHz herunterrechnen
    R->>O: Aufnahme rec/{id} eintragen
    O-->>N: Status „wartet auf Netz“
    Note over O: Upload startet, sobald WLAN da ist und die App läuft
```

1. A halten: Recorder nimmt in ein Sample auf.
2. A loslassen: Sample wird als WAV gespeichert, heruntergerechnet und als `rec/<id>.raw` abgelegt. Eintrag in der Outbox, Status „wartet auf Netz“.
3. Sobald WLAN da ist und die App läuft, beginnt die Outbox mit dem Upload.

### Szenario B: Upload und Ausführung

```mermaid
sequenceDiagram
    participant O as Outbox (Playdate)
    participant G as Gateway
    participant Q as Queue
    participant T as Transkription
    participant A as Agent-Worker
    participant I as Inbox (Playdate)
    O->>G: GET /rec/{id}
    G-->>O: vorhandene Chunks
    loop fehlende Chunks
        O->>G: PUT /rec/{id}/chunk/{n}
    end
    O->>G: POST /rec/{id}/done
    G->>Q: Eintrag „received“
    G-->>O: Quittung „abgelegt“
    Q->>T: Audio
    T->>Q: Text, Statuskarte „Verstanden: …“
    A->>Q: Batch holen
    A->>A: Claude Code verarbeitet
    A->>G: Karten
    I->>G: GET /inbox?since=
    G-->>I: neue Karten
```

1. Outbox fragt `GET /rec/{id}` und erfährt, welche Chunks der Server schon hat.
2. Fehlende Chunks werden per `PUT` gesendet.
3. `POST /rec/{id}/done` mit Samplerate. Server baut eine WAV-Datei, transkribiert und legt eine Statuskarte „Verstanden: …“ in die Inbox.
4. Der Agent-Worker übernimmt den Job und erzeugt eine oder mehrere Karten.
5. Der Playdate pollt die Inbox, lädt fehlende Assets und rendert.

### Szenario C: Interaktion

```mermaid
sequenceDiagram
    actor N as Nutzer
    participant P as Playdate
    participant G as Gateway
    participant A as Agent-Worker
    G-->>P: Karte mit Auswahl „Deployen / Später“
    N->>P: wählt „Deployen“
    P->>G: POST /interaction
    G->>A: neuer Job in derselben Session
    A->>G: Folgekarte
    P->>G: GET /inbox?since=
    G-->>P: Folgekarte
```

1. Karte bietet Auswahl, z. B. „Deployen / Später“.
2. Auswahl wird über die Outbox an `/interaction` gesendet.
3. Der Server legt einen Job an, der Agent antwortet in derselben Session mit einer neuen Karte.

### Szenario D: Asynchrone Abarbeitung und leere Quota

```mermaid
sequenceDiagram
    participant G as Gateway
    participant Q as Queue
    participant A as Arborist
    participant S as Scheduler
    G->>Q: Idee 1 ablegen
    G->>Q: Idee 2 ablegen
    A->>Q: Batch holen
    Q-->>A: Idee 1, Idee 2
    A->>A: nach Projekt gruppieren und bearbeiten
    alt Quota reicht
        A->>Q: beide „done“
        A->>G: Karten und Lagebild
    else Quota aufgebraucht
        A->>Q: Rest „parked“
        Note over A: pausiert bis zum Reset
        G->>Q: neue Ideen werden weiter abgelegt
    end
    S->>A: nachts Wartung starten
    A->>Q: Tagesverlauf lesen
    A->>A: Zusammenfassen, Gedächtnis pflegen, nächsten Tag planen
```

## 7. Verteilungssicht

| Variante | Server läuft auf | Erreichbarkeit | Zweck |
| --- | --- | --- | --- |
| POC | Lokaler Rechner (Linux, macOS, WSL2) | LAN, HTTP mit Token | Ablauf und Latenz testen |
| V2 | Azure-VM (z. B. B2s, 2 vCPU, 4 GB RAM), per Pulumi provisioniert, Docker | HTTPS über Reverse Proxy, nur Port 443 | Dauerbetrieb |

In V2 läuft der Server als Docker-Container, je Instanz ein eigener Satz.

```mermaid
flowchart TB
    subgraph Geräte
        PD[Playdate]
        WEB[Browser / Handy]
    end

    subgraph Azure[Azure, per Pulumi provisioniert]
        subgraph VM[Linux-VM, z. B. B2s]
            RP[Reverse Proxy<br/>HTTPS, Port 443]
            subgraph Docker[Docker, je Instanz ein Satz]
                GW[Device-Gateway]
                IN[Intake-Agent]
                AR[Arborist<br/>Claude Code]
                BR[Tool-Broker]
                DB[(SQLite-Volume)]
            end
            SCH[Scheduler]
        end
        KV[Key Vault<br/>Broker-Secrets]
    end

    ANT[Anthropic]
    EXT[Externe Dienste]

    PD & WEB -->|HTTPS| RP --> GW
    GW --- DB
    IN --- DB
    AR --- DB
    AR -->|MCP| BR --> EXT
    BR -.-> KV
    AR --> ANT
    SCH --> AR
```

Netzwerk: Der Arborist-Container darf nur zum Broker und zu Anthropic. Nur der Reverse Proxy ist von außen erreichbar. Für den POC reicht ein Prozess.

## 8. Querschnittliche Konzepte

### Audioformat

- Aufnahme: 44,1 kHz, 8 Bit mono im Playdate-Sample.
- Upload: jedes 5. Sample, also ca. 8,8 kHz, 8 Bit unsigned, roh (ca. 8,8 KB/s).
- Chunkgröße: 8 KB.
- Server: wandelt zu 16-Bit-WAV, Whisper rechnet auf 16 kHz um.
- Später optional: Tiefpass vor dem Downsampling und IMA-ADPCM in C (halbiert die Datenmenge).

### Karten

Siehe [`karten-dsl.md`](karten-dsl.md). Kernregeln: eine Kernaussage pro Karte, maximal sechs Zeilen à 40 Zeichen, Details als Folgekarten.

### Agent-Anweisung

Der System-Prompt des Agenten liegt nicht im Repo, sondern in einer Datei, auf die `PDC_AGENT_PROMPT` zeigt. Er erklärt die Karten-DSL und verlangt am Ende jeder Antwort eine Zeile `CARD: <JSON>`. Eine Beispielanweisung liegt in `server/agent_prompt.example.md`.

### Sicherheit

- Gerätetoken im Header `X-Token`.
- POC nur im LAN. V2 nur über HTTPS, Port 443, Rate-Limit am Reverse Proxy.
- Claude-Code-Berechtigungen über `settings.json` des Agent-Arbeitsverzeichnisses einschränken.
- Instanzen strikt trennen. Eine Arbeits-Instanz nur mit Freigabe des Arbeitgebers betreiben; dienstliche Daten nie in einer privaten Instanz.

## 9. Architekturentscheidungen

| ADR | Entscheidung | Begründung |
| --- | --- | --- |
| 1 | Transkription lokal mit Whisper | Datenschutz, keine Audio-Cloud |
| 2 | Chunked Upload statt Streaming | Playdate-Netz unzuverlässig, Wiederaufnahme nötig |
| 3 | Polling statt Push (für den Playdate) | Kein Push-Kanal auf dem Playdate; App muss ohnehin offen sein. Andere Geräte bekommen Push über das Device-Gateway |
| 4 | Deklarative Karten-DSL | Neue Darstellungen ohne Client-Update |
| 5 | Erst lokaler POC, dann VM | Ablauf testen, bevor Kosten entstehen |
| 6 | Downsampling in Lua im POC | Schnell umsetzbar; C nur, wenn zu langsam |
| 7 | Transkription als austauschbarer Provider (ergänzt ADR 1) | Voxtral-API ist günstig (ca. 0,24 $/h) und gut; lokal bleibt Standard für maximalen Datenschutz |
| 8 | V2 auf Azure-VM mit Docker, IaC mit Pulumi | Dauerhafte Shell für Claude Code; reproduzierbar; Container Instances eher für kurze Jobs |
| 9 | Externe Tools nur über einen Rechte- und Tool-Broker | Tokens bleiben außerhalb des Agenten; granulare Rechte und Protokoll pro Tool |

## 10. Qualitätsszenarien

- 10 s Sprache offline aufgenommen, später WLAN: vollständig hochgeladen in < 15 s.
- WLAN reißt bei Chunk 5 von 10 ab: Upload setzt bei Chunk 6 fort, keine Duplikate.
- Agent liefert kaputtes JSON: Nutzer sieht eine lesbare Textkarte.
- Server neu gestartet: offene Jobs werden fortgesetzt, Inbox bleibt erhalten.

## 11. Risiken und technische Schulden

| Risiko | Auswirkung | Gegenmaßnahme |
| --- | --- | --- |
| Downsampling in Lua zu langsam | Hänger nach der Aufnahme | Schrittweise pro Frame oder in C |
| HTTP-Body-Limits auf dem Playdate | Upload scheitert | Kleine Chunks, Größe empirisch ermitteln |
| Netzwerk nur bei offener App | Kein echter Hintergrund-Upload | Outbox beim App-Start, Hinweis in der UI |
| Lange Agent-Laufzeiten | Warten ohne Feedback | Statuskarten für jeden Zustand |
| Kosten und Limits von Claude | Dauerbetrieb teuer | Leerlauf ohne Aufrufe, Limits beobachten |
| Aliasing ohne Tiefpass | Schlechtere Erkennung | Erst messen, dann ggf. Filter |

## 12. POC-Scope

- [ ] Server lokal: Chunk-Ingest, Whisper, Queue, Echo- und Claude-Agent
- [ ] `tools/fake_playdate.py` für Tests ohne Hardware
- [ ] Playdate: Aufnahme mit A, Downsampling, Outbox mit Chunks und Retry
- [ ] Inbox-Polling und Renderer für `text`, `list`, `icon`, `bar`, `choices`
- [ ] Messung: Zeit vom Loslassen bis zur ersten Karte

Nicht im POC: vom Agenten erzeugte Tilesets, Animationen, VM, HTTPS.
