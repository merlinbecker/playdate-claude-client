# Meilenstein 1: Bootstrap – Arborist läuft in der Cloud

Ziel: So schnell wie möglich ein Claude Code, das dauerhaft auf einer Azure-VM läuft und sich vom Handy aus bedienen lässt – auch per Sprache. Der Rundlauf muss nicht perfekt sein. Wichtig ist, dass der Agent ab dann **sich selbst weiterbauen kann**: Gateway, Queue, Dashboard und Playdate-Anbindung entstehen in Gesprächen mit genau diesem Agenten.

## Idee

Für den Anfang wird nichts Eigenes gebaut, um an den Agenten heranzukommen. Claude Code bringt dafür **Remote Control** mit: Eine Claude-Code-Sitzung läuft auf der VM, und man steuert sie über [claude.ai/code](https://claude.ai/code) oder die Claude-App auf dem Handy. Remote Control gibt es für Pro- und Max-Abos und braucht keine eingehenden Verbindungen – die VM verbindet sich nur nach außen zu Anthropic.

```mermaid
flowchart LR
    H[Handy<br/>Claude-App, Diktat] --> A[Anthropic<br/>Remote Control]
    B[Browser<br/>claude.ai/code] --> A
    S[Laptop<br/>SSH] --> VM
    A <-->|nur ausgehend| VM

    subgraph VM[Azure-VM]
        T[systemd + tmux] --> C[Concierge]
        T --> RA[Rollen-Agent A<br/>z. B. Wissen]
        T --> RB[Rollen-Agent B<br/>z. B. Bauen]
        C -->|Inbox| RA & RB
        RA & RB -->|Inbox| C
    end
```

## Schritte

1. **VM per Pulumi**
   - Linux-VM (z. B. Ubuntu LTS, B2s: 2 vCPU, 4 GB RAM), verwalteter Datenträger für den Workspace.
   - Keine eingehenden Ports außer SSH, und SSH nur von der eigenen IP oder über Azure Bastion bzw. ein privates VPN.
   - Auto-Shutdown aus (der Agent soll laufen), Budget-Alarm an.
   - Cloud-Init: Git, tmux, Python, Node, Docker.
2. **Claude Code installieren** nach der offiziellen Anleitung und einmal per SSH `claude` starten, mit `/login` über claude.ai anmelden. Kein `ANTHROPIC_API_KEY` setzen, sonst wird über die API abgerechnet.
3. **Workspaces für die Rollen anlegen** (Konzept: [`rollen.md`](rollen.md))
   - Ein Workspace pro Rolle mit eigener `CLAUDE.md` und Ordner `inbox/`: der Concierge und die Rollen-Agenten, z. B. einer für Wissen und einer für Code-Projekte. Rollen-Agenten arbeiten in ihrem eigenen Repo.
   - Dieses Repo klonen; GitHub-Zugang mit einem fein eingeschränkten Token nur für die eigenen Projekt-Repos.
   - Persönliche Workspaces und Inboxen sind privat und gehören nicht in dieses Repo.
4. **Sitzungen starten**
   - Pro Rolle einmal von Hand im Workspace `claude --remote-control <rolle>` starten und die Rückfrage für Remote Control bestätigen.
   - Dann pro Rolle eine systemd-Unit, die beim Hochfahren in einer tmux-Sitzung `claude --continue --remote-control <rolle>` startet und nach einem Absturz neu startet. So kommen nach einem Neustart der VM alle Sitzungen mit ihrem letzten Verlauf zurück.
   - Einen Watcher einrichten, der eine Sitzung per `tmux send-keys` weckt, sobald in ihrer Inbox ein neuer Auftrag liegt.
5. **Vom Handy verbinden**
   - Im Alltag mit der Concierge-Sitzung sprechen; die Rollen-Sitzungen nur für längere Arbeit direkt öffnen.
   - Sprechen über die Diktierfunktion von Handy bzw. App.
   - Benachrichtigungen erlauben: Der Agent meldet sich, wenn eine lange Aufgabe fertig ist oder er eine Entscheidung braucht.
   - **Trusted Devices** in den Kontoeinstellungen einschalten, damit nur bestätigte Geräte die Sitzung steuern dürfen.

## Was damit schon geht

- Ideen und Aufgaben per Sprache vom Handy abladen; der Agent pflegt To-do- und Notizdateien im privaten Workspace.
- Am Repo weiterbauen: Gateway, Queue, Web-Dashboard, Playdate-Server.
- Mehrere Rollen parallel, die sich über Inboxen Aufträge zuschieben.

## Bewusste Abkürzungen

| Abkürzung | Später ersetzt durch |
| --- | --- |
| Claude-App statt eigener Geräte | Device-Gateway mit Playdate, Web-Dashboard, Brille, E-Ink |
| Kein Broker, nur GitHub-Token mit engem Scope | Rechte- und Tool-Broker |
| Dateien statt Queue | Eingangs-Queue |
| Diktat des Handys statt Intake-Agent | Intake-Agent mit Whisper oder Voxtral |
| Inbox-Dateien und `tmux send-keys` | Eingangs-Queue und Gateway |

Die Zielarchitektur ([`arc42.md`](arc42.md)) bleibt unverändert. Remote Control ist der Zugang für den Bau und bleibt auch später als Notfall- und Admin-Zugang erhalten.

## Risiken

- **Shell mit Zugangsdaten:** Bis der Broker steht, liegt das GitHub-Token auf der VM. Deshalb nur ein eng eingeschränktes Token und keine weiteren Zugänge.
- **Sitzungsinhalte bei Anthropic:** Während Remote Control verbunden ist, liegt das Transkript der Sitzung auf den Servern von Anthropic. Keine dienstlichen Daten.
- **Abo-Limits:** Gilt wie im Dauerbetrieb, siehe [`vision.md`](vision.md).
