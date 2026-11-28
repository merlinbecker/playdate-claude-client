# Infrastruktur

Richtet den Server für eine Pocket-Concierge-Instanz ein. Standard ist ein kleiner Server bei **Hetzner Cloud**. Gesteuert wird alles über einen GitHub-Workflow; deine persönlichen Werte liegen als Secrets und Variablen in GitHub, nicht im Repo. So kann das Repo öffentlich bleiben.

## Was entsteht

| Ressource | Zweck |
| --- | --- |
| Firewall | Eingehend kein SSH, nur Tailscale (UDP 41641) und Ping; ausgehend alles |
| Server | Ubuntu 24.04, Standard `cx23` (2 vCPU, 4 GB) in Nürnberg, mit Backups |

**Zugang nur über Tailscale.** Der Server tritt beim ersten Start mit einem Auth-Key deinem privaten Tailscale-Netz bei. Du erreichst ihn dann von jedem deiner Geräte mit `ssh pocket@pocket-concierge`, ohne SSH-Schlüssel und ohne IP-Freigaben. Von außen ist kein Anmelde-Port offen. Notfallzugang ist die Konsole in der Hetzner-Oberfläche; das Root-Passwort dafür schickt Hetzner beim Anlegen per Mail.

Beim ersten Start richtet Cloud-Init den Benutzer ein, klont dieses Repo nach `/opt/pocket-concierge` und ruft [`host/setup-host.sh`](../host/setup-host.sh) auf. Das installiert Claude Code, legt die Rollen an und startet die Sitzungen als systemd-Dienste (siehe [`docs/rollen.md`](../docs/rollen.md)).

Der Server wird bei späteren Läufen **nicht neu gebaut**, auch wenn sich Cloud-Init ändert. Sitzungen, Anmeldungen und Inboxen bleiben so erhalten. Änderungen am Host holst du auf dem Server mit `sudo pocket-update`.

## Einrichten

### 1. Konten

- **Hetzner Cloud:** Projekt anlegen, unter *Security → API Tokens* ein Token mit Lese- und Schreibrecht erzeugen.
- **Pulumi Cloud** (kostenlos für Einzelpersonen, Anmeldung mit GitHub) für den Zustand der Infrastruktur: unter *Personal access tokens* ein Token erzeugen. Alternativ ein eigenes Backend, siehe unten.
- **Tailscale** (Personal-Plan kostenlos): Tailscale auf Laptop und Handy installieren und anmelden. In der Admin-Konsole unter *Settings → Keys* einen **Auth-Key** erzeugen: nicht wiederverwendbar, nicht ephemeral. Er ist nur für den ersten Start nötig und wird danach auf dem Server gelöscht.

### 2. GitHub-Umgebung „infra“

Im Repo unter *Settings → Environments* die Umgebung **`infra`** anlegen. Optional „Required reviewers“ setzen, dann muss jeder Lauf bestätigt werden.

**Secrets** (bleiben verborgen, auch in Logs):

| Name | Inhalt | Pflicht |
| --- | --- | --- |
| `HCLOUD_TOKEN` | Hetzner-API-Token | ja |
| `PULUMI_ACCESS_TOKEN` | Pulumi-Cloud-Token | ja, außer bei eigenem Backend |
| `POCKET_CONCIERGE_TAILSCALE_AUTHKEY` | Tailscale-Auth-Key (`tskey-auth-…`) | ja |
| `POCKET_CONCIERGE_ROLE_REPOS` | Zeilen `rolle=git-url` für Rollen mit eigenem Repo | nein |
| `PULUMI_CONFIG_PASSPHRASE` | Nur bei eigenem Backend | nein |

**Variablen:**

| Name | Inhalt | Standard |
| --- | --- | --- |
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
2. `up` legt den Server an. Nach ein paar Minuten erscheint er in der Tailscale-Admin-Konsole als `pocket-concierge`. Dort für ihn **Disable key expiry** wählen, sonst fällt er nach einigen Monaten aus dem Netz.
3. `destroy` baut alles wieder ab.

Der Workflow läuft nur, wenn du ihn als Besitzer des Repos startest. Forks bekommen keine Secrets.

### 4. Auf dem Server

```bash
ssh pocket@pocket-concierge     # von einem Gerät in deinem Tailnet
pocket-status                   # Rollen, offene Aufträge, Quota-Pause
tmux -L pocket-concierge attach # in der Sitzung /login ausführen, Remote Control bestätigen
```

Lösen vom tmux-Fenster: `Strg+b`, dann `d`. Das gleiche für jede weitere Rolle. Danach erscheinen die Sitzungen in der Claude-App.

Bei der ersten Anmeldung per Tailscale SSH fragt Tailscale eventuell im Browser nach einer Bestätigung („check mode“). Ist der Server nach 5 Minuten nicht im Tailnet, war der Auth-Key meist abgelaufen oder schon benutzt: In der Hetzner-Konsole als root einloggen, neuen Key nach `/etc/pocket-concierge/tailscale-authkey` schreiben und `bash /opt/pocket-concierge/host/setup-host.sh` ausführen.

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

`infra/__main__.py` wählt den Anbieter über `pocket-concierge:provider`. Umgesetzt ist `hetzner`. Ein weiterer Anbieter ist eine weitere Funktion, die Firewall und Server mit derselben Cloud-Init-Konfiguration anlegt. Alles ab `host/` ist anbieterunabhängig und läuft auf jedem Ubuntu-Server, auch auf einem Raspberry Pi: Cloud-Init-Schritte von Hand ausführen und dann `host/setup-host.sh` starten.
