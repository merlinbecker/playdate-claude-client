# Vision und Konzept: Agenten-Hub

> Ergänzt [`arc42.md`](arc42.md). Dort steht die Architektur des Playdate-POC, hier die Zielvision darüber hinaus.

## 1. Vision

Ein **dauerhaft laufender Claude-Code-Agent in der Cloud**, der laufend mit Eingaben gefüttert wird – Sprache, Text, Ereignisse – und seine Ergebnisse an **mehrere Ausgabegeräte** verteilt. Was wohin geht, hängt davon ab, welche Geräte gerade online sind und worum es gerade geht.

Der Playdate ist dabei **ein Client unter mehreren**, nicht das Zentrum. Das Repo bleibt generisch, damit andere den Stack mit ihren eigenen Geräten und Agenten betreiben können.

## 2. Leitprinzipien

- **Generisch und öffentlich:** Das Repo enthält Infrastruktur, Protokolle und Beispiel-Agenten. Persönliche Inhalte, Prompts, Hostnamen und Tokens gehören nicht hinein.
- **Mehrere Instanzen:** Derselbe Stack lässt sich mehrfach betreiben, z. B. eine private und eine für die Arbeit. Instanzen sind vollständig getrennt: eigene Container, Secrets, Daten und Claude-Zugänge.
- **Sprache rein, Karten raus:** Spracheingabe ja, Sprachausgabe nein. Ausgaben sind geräte-spezifische Darstellungen, auf dem Playdate z. B. Karten nach der [Karten-DSL](karten-dsl.md).
- **Thin Clients:** Geräte puffern, laden hoch, holen ab und rendern. Logik liegt auf dem Server.
- **Austauschbare Transkription:** Lokal mit Whisper oder über eine API wie Voxtral – pro Instanz konfigurierbar.
- **Infrastructure as Code:** Die Cloud-Umgebung wird mit Pulumi beschrieben und ist reproduzierbar.

## 3. Bausteine

| Baustein | Aufgabe |
| --- | --- |
| Ingest-API | Nimmt Audio, Text und Interaktionen von Geräten entgegen (chunked, idempotent, siehe arc42) |
| Transkription | Audio → Text. Provider wählbar: `whisper` (lokal) oder `voxtral` (Mistral-API, Batch) |
| Message-Hub | Drehscheibe zwischen Eingängen, Agenten und Geräten. Ein Kanal pro Gerät bzw. Thema |
| Agent-Worker | Claude Code CLI mit fortgesetzter Session; verarbeitet Aufträge |
| Verteil-Agenten | Laufen periodisch, fassen das aktuelle Thema zusammen und legen passende Ausgaben in die Gerätekanäle |
| Geräte-Registry | Kennt die Geräte, ihren Online-Status (letzter Abruf) und ihre Fähigkeiten |
| Ausgabe-Adapter | Übersetzen Agenten-Ergebnisse ins Format des Geräts (Karte, E-Ink-Bild, HTML) |

## 4. Geräte

| Gerät | Rolle | Eingabe | Ausgabe |
| --- | --- | --- | --- |
| Playdate | Interaktives Agenten-Terminal | Sprache (offline gepuffert), Auswahl per Kurbel/Tasten | Dynamische 1-Bit-Karten mit Tilesets, Animation, Antwortauswahl |
| E-Ink-Display | Passive Anzeige | – | Status, aktuelles Thema, Zusammenfassungen |
| Arborist-Website | Web-Ansicht | optional | Verlauf, aktuelle Themen, Agenten-Status |
| Weitere | über Adapter | | |

Neue Geräte brauchen nur einen Eintrag in der Registry und einen Ausgabe-Adapter.

## 5. Datenfluss

1. Ein Gerät sendet Audio oder Text an die Ingest-API.
2. Audio wird vom konfigurierten Provider transkribiert.
3. Der Text landet als Nachricht im Message-Hub.
4. Der Agent-Worker verarbeitet den Auftrag und erzeugt Ergebnisse.
5. Verteil-Agenten prüfen periodisch, welche Geräte online sind, und legen passende Ausgaben in deren Kanäle.
6. Geräte holen ihren Kanal ab (Pull mit `since`-Cursor) und stellen die Inhalte dar.

## 6. Betrieb

| Variante | Plattform | Zweck |
| --- | --- | --- |
| POC | Lokaler Rechner im LAN | Ablauf und Latenz testen (siehe [`poc-setup.md`](poc-setup.md)) |
| V2 | Azure-VM (z. B. B2s: 2 vCPU, 4 GB RAM) mit Docker | Dauerbetrieb, je Instanz ein eigener Container-Satz |
| Alternative | Raspberry Pi ab Modell 4 (64 Bit, ≥ 4 GB RAM) mit Docker | Günstiger Heimbetrieb |

- **VM statt Container Instances:** Claude Code braucht eine dauerhafte Shell mit Dateisystem und Git-Arbeitskopien; Container Instances passen besser zu kurzlebigen Jobs.
- **Provisionierung mit Pulumi:** VM, Netzwerk, Firewall (nur 443), Secrets, Auto-Shutdown optional.
- **Ältere Raspberry Pis** (z. B. Pi 2, 32 Bit, 1 GB RAM) sind ungeeignet.

## 7. Vorgehen

1. **POC lokal:** Sprach-Upload vom Playdate, Karten zurück, einfacher Antwort-Agent.
2. **Cloud-Basis:** Azure-VM per Pulumi, Docker, Server als Dienst, HTTPS.
3. **Hub und Transkription:** Message-Hub, Transkriptions-Provider umschaltbar.
4. **Weitere Geräte:** E-Ink-Display, Arborist-Website.
5. **Multi-Instanz:** Konfiguration pro Instanz, Trennung privat/Arbeit.

## 8. Offene Fragen

- **Abrechnung:** Claude Code im Dauerbetrieb über Abo oder API-Key – Nutzungsbedingungen prüfen.
- **Message-Hub:** SQLite-Queue weiterverwenden, Redis, NATS oder Azure Service Bus?
- **Geräte-Auth:** Token pro Gerät und Instanz, Rotation.
- **Arbeits-Instanz:** Nur mit Freigabe des Arbeitgebers betreiben; Datenschutz und Compliance klären, bevor dienstliche Daten oder Audio an externe Dienste gehen.
