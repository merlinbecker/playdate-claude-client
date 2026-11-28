# Infrastruktur

Richtet den Server für eine Pocket-Concierge-Instanz ein. Standard ist ein kleiner Server bei **Hetzner Cloud**. Gesteuert wird alles über einen GitHub-Workflow; deine persönlichen Werte liegen als Secrets und Variablen in GitHub, nicht im Repo. So kann das Repo öffentlich bleiben.

## Was entsteht

| Ressource | Zweck |
| --- | --- |
| SSH-Key | Dein öffentlicher Schlüssel für den Admin-Zugang |
| Firewall | Eingehend nur SSH von deinen IP-Adressen; ausgehend alles (Remote Control braucht nur ausgehende Verbindungen) |
| Server | Ubuntu 24.04, Standard `cx23` (2 vCPU, 4 GB) in Nürnberg, mit Backups |

Beim ersten Start richtet Cloud-Init den Benutzer ein, klont dieses Repo nach `/opt/pocket-concierge` und ruft [`host/setup-host.sh`](../host/setup-host.sh) auf. Das installiert Claude Code, legt die Rollen an und startet die Sitzungen als systemd-Dienste (siehe [`docs/rollen.md`](../docs/rollen.md)).

Der Server wird bei späteren Läufen **nicht neu gebaut**, auch wenn sich Cloud-Init ändert. Sitzungen, Anmeldungen und Inboxen bleiben so erhalten. Änderungen am Host holst du auf dem Server mit `sudo pocket-update`.

## Einrichten

### 1. Konten

- **Hetzner Cloud:** Projekt anlegen, unter *Security → API Tokens* ein Token mit Lese- und Schreibrecht erzeugen.
- **Pulumi Cloud** (kostenlos für Einzelpersonen) für den Zustand der Infrastruktur: unter *Personal access tokens* ein Token erzeugen. Alternativ ein eigenes Backend, siehe unten.

### 2. GitHub-Umgebung „infra“

Im Repo unter *Settings → Environments* die Umgebung **`infra`** anlegen. Optional „Required reviewers“ setzen, dann muss jeder Lauf bestätigt werden.

**Secrets** (bleiben verborgen, auch in Logs):

| Name | Inhalt | Pflicht |
| --- | --- | --- |
| `HCLOUD_TOKEN` | Hetzner-API-Token | ja |
| `PULUMI_ACCESS_TOKEN` | Pulumi-Cloud-Token | ja, außer bei eigenem Backend |
| `POCKET_CONCIERGE_SSH_ALLOWED_CIDRS` | IP-Adressen, die SSH dürfen, z. B. `203.0.113.7/32`, mehrere mit Komma | ja |
| `POCKET_CONCIERGE_ROLE_REPOS` | Zeilen `rolle=git-url` für Rollen mit eigenem Repo | nein |
| `PULUMI_CONFIG_PASSPHRASE` | Nur bei eigenem Backend | nein |

**Variablen:**

| Name | Inhalt | Standard |
| --- | --- | --- |
| `POCKET_CONCIERGE_SSH_PUBLIC_KEY` | Öffentlicher SSH-Schlüssel (`ssh-ed25519 …`) | Pflicht |
| `POCKET_CONCIERGE_ROLES` | Rollen, mit Komma getrennt; `concierge` muss dabei sein | `concierge` |
| `POCKET_CONCIERGE_LOCATION` | `nbg1`, `fsn1` oder `hel1` | `nbg1` |
| `POCKET_CONCIERGE_SERVER_TYPE` | z. B. `cx23`, `cax11` (ARM), `cpx22` | `cx23` |
| `POCKET_CONCIERGE_BACKUPS` | `true` oder `false` | `true` |
| `POCKET_CONCIERGE_SWAP_GB` | Swap-Größe | `2` |
| `POCKET_CONCIERGE_REPO_REF` | Branch, den der Server auscheckt | `main` |
| `PULUMI_BACKEND_URL` | Eigenes Backend statt Pulumi Cloud | leer |

### 3. Workflow starten

*Actions → Infrastruktur → Run workflow*:

1. `preview` zeigt, was entstehen würde.
2. `up` legt den Server an. Die IP-Adresse steht in der Hetzner-Konsole; im öffentlichen Log ist sie maskiert.
3. `destroy` baut alles wieder ab.

Der Workflow läuft nur, wenn du ihn als Besitzer des Repos startest. Forks bekommen keine Secrets.

### 4. Auf dem Server

```bash
ssh pocket@<IP>
cloud-init status --wait          # warten, bis die Einrichtung fertig ist
pocket-status                   # Rollen, offene Aufträge, Quota-Pause
tmux -L pocket-concierge attach # in der Sitzung /login ausführen, Remote Control bestätigen
```

Lösen vom tmux-Fenster: `Strg+b`, dann `d`. Das gleiche für jede weitere Rolle. Danach erscheinen die Sitzungen in der Claude-App.

### Rollen mit eigenem Repo

Steht eine Rolle in `POCKET_CONCIERGE_ROLE_REPOS`, wird ihr Repo nach `~/roles/<rolle>` geklont. Für private Repos braucht der Server einen Deploy-Key:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""   # auf dem Server, als pocket
cat ~/.ssh/id_ed25519.pub                          # bei GitHub als Deploy-Key des Repos eintragen
rm -rf ~/roles/<rolle> && sudo pocket-update     # erneut klonen
```

## Lokal testen

```bash
cd infra
python3 -m venv venv && venv/bin/pip install -r requirements.txt pytest
venv/bin/python -m pytest -q
```

Die Tests laufen ohne Cloud-Konto mit Pulumi-Mocks.

## Eigenes Backend

Statt Pulumi Cloud geht jedes S3-kompatible Backend, etwa Hetzner Object Storage. Dann `PULUMI_BACKEND_URL` (z. B. `s3://bucket?endpoint=…`) als Variable setzen, `PULUMI_CONFIG_PASSPHRASE` als Secret und die S3-Zugangsdaten als `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` im Workflow ergänzen.

## Weitere Anbieter

`infra/__main__.py` wählt den Anbieter über `pocket-concierge:provider`. Umgesetzt ist `hetzner`. Ein weiterer Anbieter ist eine weitere Funktion, die SSH-Key, Firewall und Server mit derselben Cloud-Init-Konfiguration anlegt. Alles ab `host/` ist anbieterunabhängig und läuft auf jedem Ubuntu-Server, auch auf einem Raspberry Pi: Cloud-Init-Schritte von Hand ausführen und dann `host/setup-host.sh` starten.
