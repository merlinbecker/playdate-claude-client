# Runbook: Einrichtung fortsetzen (für den Concierge)

Dieses Runbook führt der **Concierge** selbst aus, sobald er läuft und angemeldet ist. Es richtet eine Bau-Rolle ein, verbindet GitHub und macht das Gedächtnis des Concierge zu einem privaten Repo. Der Nutzer muss nur zwei Schritte selbst erledigen; dort hältst du an.

## Eingaben vom Nutzer

Diese Werte nennt der Nutzer im Auftrag. Fehlt einer, frag einmal danach, bevor du anfängst:

| Wert | Beispiel |
| --- | --- |
| `BAU` – Name der Bau-Rolle | `meinbauer` |
| `GH_USER` – GitHub-Benutzer | `octocat` |
| `MEMORY_REPO` – Name des privaten Gedächtnis-Repos | `concierge-privat` |
| `REPO` – Repo dieses Systems | `<GH_USER>/pocket-concierge` |

## Regeln für dich

- **Idempotent:** Prüf vor jedem Schritt, ob er schon erledigt ist, und überspring ihn dann.
- **Fortschritt festhalten** in `~/roles/concierge/lokal/einrichtung.md` (Schritt, erledigt/offen, Datum). Bei einem neuen Anlauf liest du dort weiter.
- **Nutzer-Schritte** (markiert mit 👤): dem Nutzer kurz und genau sagen, was zu tun ist, dann **anhalten** und auf seine Rückmeldung warten.
- **Nie nach Tokens oder Passwörtern im Chat fragen.** Chatverläufe werden gespeichert. Tokens gibt der Nutzer nur im Terminal ein.
- Antworte im Cheat-Sheet-Format: Kernaussage, wenige Zeilen, nächste Schritte nummeriert.
- Bei einem Fehler: anhalten, Fehler in zwei Sätzen erklären, Vorschlag machen. Nichts mit `--force` oder Löschen „reparieren“.

## Schritte

### 1. Ausgangslage prüfen

```bash
whoami                      # pocket
sudo -n true && echo sudo-ok
pocket-status
```

### 2. Neuesten Stand holen

```bash
sudo pocket-update
```

### 3. Bau-Rolle anlegen

```bash
ENV=/etc/pocket-concierge/pocket-concierge.env
grep -E '^POCKET_CONCIERGE_ROLES=' "$ENV"
```

- Steht `BAU` noch nicht in `POCKET_CONCIERGE_ROLES`, ergänzen (Leerzeichen-getrennt, in einfachen Anführungszeichen), z. B. per `sudo sed -i`.
- Gibt es keine Zeile `POCKET_CONCIERGE_ROLE_TYPES`, anhängen: `echo "POCKET_CONCIERGE_ROLE_TYPES='<BAU>=bauen'" | sudo tee -a "$ENV"`. Gibt es sie, `<BAU>=bauen` ergänzen.
- Dann `sudo pocket-update` und `pocket-status`: `<BAU>` muss `active` sein.
- Prüf `~/roles/<BAU>/CLAUDE.md`. Beginnt sie nicht mit `# Rolle: <BAU> (Bauen)`, wurde sie aus einer älteren Vorlage erzeugt. Dann ersetzen:
  `sed 's/@ROLE@/<BAU>/g' /opt/pocket-concierge/host/templates/bauen/CLAUDE.md > ~/roles/<BAU>/CLAUDE.md`
- Schau mit `tmux -L pocket-<BAU> capture-pane -p -t <BAU> | tail -20` in die neue Sitzung. Wartet sie auf eine Bestätigung für Remote Control oder eine Anmeldung, sag es dem Nutzer (👤: `tmux -L pocket-<BAU> attach`, bestätigen, `Strg+b`, `d`).

### 4. 👤 GitHub vorbereiten (Nutzer)

Bitte den Nutzer, am Rechner in GitHub:

1. Ein **leeres, privates** Repo `<MEMORY_REPO>` anlegen (ohne README, ohne .gitignore).
2. Ein **fine-grained Personal Access Token** anlegen: Profilbild → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token.
   - Name z. B. „pocket-concierge-server“, Ablauf 90 Tage.
   - Repository access: **Only select repositories** → `pocket-concierge` und `<MEMORY_REPO>`.
   - Repository permissions: **Contents**, **Pull requests**, **Issues** jeweils *Read and write*.
3. Das Token **nicht in den Chat**, sondern im Terminal eingeben – im Browser-Terminal von Tailscale (Admin-Konsole → Maschine → SSH to machine, Benutzer `pocket`):
   `gh auth login --with-token` → Token einfügen → Enter → `Strg+D`.

Warte, bis der Nutzer „fertig“ meldet.

### 5. GitHub-Zugang prüfen und Git einrichten

```bash
gh auth status
gh auth setup-git
login=$(gh api user -q .login); id=$(gh api user -q .id)
git config --global user.name "Pocket Concierge"
git config --global user.email "${id}+${login}@users.noreply.github.com"
```

Schlägt `gh auth status` fehl, zurück zu Schritt 4.

### 6. Erstes Projekt für die Bau-Rolle

```bash
cd ~/roles/<BAU>
[ -d pocket-concierge ] || gh repo clone <REPO>
```

Leg `~/roles/<BAU>/projekte.md` an, falls sie fehlt, mit einer Zeile für `pocket-concierge` (Zweck: das System selbst weiterbauen).

### 7. Gedächtnis des Concierge einrichten

1. Lies in `/opt/pocket-concierge/host/templates/concierge/CLAUDE.md` die Abschnitte „Gedächtnis“ und „Pocket Concierge weiterentwickeln“ und übernimm sie in deine eigene `CLAUDE.md`. Behalte alles, was der Nutzer schon angepasst hat.
2. Leg fehlende Dateien an: `ich.md`, `todos.md`, `lagebild.md`, `tagebuch/`, `lokal/`.
3. Mach dein Verzeichnis zum Repo:

   ```bash
   cd ~/roles/concierge
   [ -d .git ] || git init -b main
   for p in inbox/ lokal/; do grep -qx "$p" .git/info/exclude || echo "$p" >> .git/info/exclude; done
   gh repo view <GH_USER>/<MEMORY_REPO> --json visibility -q .visibility   # muss PRIVATE sein
   git remote get-url origin 2>/dev/null || git remote add origin https://github.com/<GH_USER>/<MEMORY_REPO>.git
   git add -A && git commit -m "Gedächtnis: Start" && git push -u origin main
   ```

   Ist das Repo nicht `PRIVATE`: **nicht pushen**, Nutzer warnen.

### 8. Abschluss

1. `pocket-status` ausführen und dem Nutzer das Ergebnis im Cheat-Sheet-Format melden.
2. Erster Auftrag an die Bau-Rolle:
   `pocket-inbox --to <BAU> "Lies im Repo pocket-concierge docs/backlog/wartungsfenster.md und schick mir einen kurzen Plan. Erst nach Freigabe bauen."`
3. In `lokal/einrichtung.md` vermerken: Einrichtung abgeschlossen.
