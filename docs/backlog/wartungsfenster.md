# Nächtliches Wartungsfenster: Claude-Code-Updates und Neustarts

Status: offen · Zuständig: Bau-Rolle

## Ziel

Der Server bleibt nachts selbstständig auf dem aktuellen Stand, ohne dass Rollen tagsüber unterbrochen werden.

## Hintergrund

- Die native Installation von Claude Code lädt Updates im Hintergrund, **wirksam werden sie aber erst beim Neustart** der Sitzung ([Setup-Doku](https://code.claude.com/docs/en/setup.md)). Die Rollen laufen tagelang durch und bleiben sonst auf der alten Version.
- `unattended-upgrades` spielt Sicherheitsupdates ein. Kernel-Updates wirken erst nach einem Reboot, den bisher niemand auslöst.
- Ein Neustart der Rollen ist unkritisch: `pocket-run` setzt mit `--continue` fort, der Stand liegt in Dateien, offene Aufträge bleiben in der Inbox, und der Watcher weckt danach erneut.

## Vorschlag (erst als kurzen Plan bestätigen lassen)

| Zeit (Standard) | Was |
| --- | --- |
| ca. 03:00 | Nachtwartung des Concierge: Tagesrückblick, Gedächtnis pflegen und pushen. Auslösen per Timer über die Inbox. |
| ca. 04:30 | Neues Skript `host/bin/pocket-maintenance`: als Rollen-Benutzer `claude update`; nur bei neuer Version die Rollen neu starten (`systemctl restart pocket-role@…`). |
| ca. 05:00 | Reboot nur, wenn `/var/run/reboot-required` existiert, über `Unattended-Upgrade::Automatic-Reboot "true"` und `Automatic-Reboot-Time`. |

## Anforderungen

- systemd-Timer und -Service, idempotent von `host/setup-host.sh` installiert. Zeiten über Variablen in `/etc/pocket-concierge/` einstellbar (z. B. `POCKET_CONCIERGE_MAINTENANCE_TIME`, `POCKET_CONCIERGE_REBOOT_TIME`), mit `RandomizedDelaySec`.
- Nachtwartung über den bestehenden Weg auslösen: `pocket-inbox --to concierge "Nachtwartung: …"`, damit der Watcher die Quota-Pause respektiert.
- Rollen nur bei neuer Claude-Code-Version neu starten; alte und neue Version ins Journal schreiben.
- `pocket-status` zeigt zusätzlich die Claude-Code-Version, die nächste Wartung und ob ein Reboot aussteht.
- Doku: `docs/rollen.md` (Dauerbetrieb), `docs/bootstrap.md` (Befehle), arc42 (Laufzeitsicht, ADR), Devlog.
- `shellcheck` grün; Ablauf lokal mit einer Attrappe testbar, wie beim Watcher.

## Offene Punkte für den Plan

- Wie erkennt man, ob eine Rolle gerade mitten in einer Aufgabe ist, um den Neustart notfalls zu verschieben?
- Während einer Quota-Pause neu starten oder warten?
- Reicht `claude update` als Benutzer, oder kollidiert es mit dem eingebauten Auto-Update?

## Ablauf

1. Bau-Rolle liest diese Datei und schickt dem Concierge einen kurzen Plan.
2. Nach Freigabe durch den Nutzer: umsetzen, testen, pushen.
3. Der Concierge fragt den Nutzer und spielt es mit `sudo pocket-update` ein.
4. Datei nach `docs/backlog/erledigt/` verschieben, Status in `docs/backlog/README.md` aktualisieren.
