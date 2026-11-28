# Pocket Concierge Constitution

Grundsätze für alle Specs, Pläne und Umsetzungen in diesem Repo. Sie fassen die Regeln aus `CLAUDE.md` zusammen; bei Widerspruch gilt diese Verfassung und `CLAUDE.md` wird angeglichen.

## Kernprinzipien

### I. Generisch und öffentlich
Das Repo ist öffentlich. Keine persönlichen Daten, Namen, Hostnamen, IP-Adressen, Rollennamen einer Instanz, Tokens oder Inbox-Inhalte. Alles Instanzspezifische kommt über Umgebungsvariablen, `/etc/pocket-concierge/` oder GitHub-Secrets. Sensible Werte in Pulumi als Secret markieren.

### II. Dünner Client
Der Client (Playdate, Web-Simulator) bleibt so dumm wie möglich. Neue Darstellungen kommen über die Karten-DSL (`docs/karten-dsl.md`), nicht über Client-Updates. Alle Logik liegt auf dem Server.

### III. Robust und asynchron
Store-and-forward mit IDs und idempotenten, fortsetzbaren Uploads. Upload, Transkription und Agent sind über eine Queue entkoppelt. Agent-Ausgaben werden immer validiert; kaputtes JSON wird zur Textkarte, nie zum Absturz.

### IV. Host idempotent und anbieterunabhängig
`host/` richtet einen Server ohne Annahmen über den Anbieter ein. Jedes Skript darf beliebig oft laufen. Host-Änderungen kommen per `sudo pocket-update` auf den Server, nie durch Neubau über Pulumi. Bash-Skripte sind `shellcheck`-sauber.

### V. Testbar ohne echte Abhängigkeiten (nicht verhandelbar)
Jede Änderung ist lokal prüfbar: Attrappen per `PATH` für `claude`, `systemctl`, `tmux` u. Ä., `PDC_AGENT=echo` für den Server, `tools/fake_playdate.py` für den Client. Hardware-Verhalten (Netzwerk, Mikrofon) gilt erst nach einem Test auf echtem Gerät als bestätigt.

### VI. Sparsam und sicher im Betrieb
Alle Rollen teilen sich eine Quota: Abläufe respektieren die Quota-Pause und wecken nicht unnötig. Externe Tools nur über den Rechte- und Tool-Broker. Spracherkennung als austauschbarer Provider; Audio geht nur an Drittanbieter, wenn die Instanz das ausdrücklich konfiguriert.

## Sprache und Doku

Doku, Kommentare, Specs und Commit-Messages auf Deutsch, Bezeichner im Code auf Englisch. Jede Funktion, die den Betrieb ändert, aktualisiert die betroffene Doku (`docs/rollen.md`, `docs/bootstrap.md`, `docs/arc42.md` mit Laufzeitsicht und ADR) und das Devlog des Tages.

## Arbeitsablauf

1. Vorhaben stehen in `docs/backlog/`. Daraus entsteht mit Spec Kit: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`. Kein Code ohne Spec und Plan.
2. Der Plan wird vor der Umsetzung freigegeben (über den Concierge bzw. den Nutzer). Weicht die Spec vom freigegebenen Vorschlag ab, erneut vorlegen.
3. Kleine Schritte: ändern, Tests und Linter, committen, pushen.
4. Nach dem Push melden, ob ein `sudo pocket-update` nötig ist.

## Governance

Diese Verfassung steht über einzelnen Specs und Plänen. Änderungen per Commit mit kurzer Begründung; Version nach SemVer (MAJOR: Prinzip entfällt oder ändert sich grundlegend, MINOR: neues Prinzip, PATCH: Klarstellung).

**Version**: 1.0.0 | **Ratified**: 2026-11-28 | **Last Amended**: 2026-11-28
