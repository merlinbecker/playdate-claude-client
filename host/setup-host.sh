#!/usr/bin/env bash
# Richtet einen Pocket-Concierge-Host ein. Idempotent: darf beliebig oft laufen.
#
# Läuft als root. Liest /etc/pocket-concierge/pocket-concierge.env (von Pulumi bzw. Cloud-Init
# geschrieben) und optional /etc/pocket-concierge/role-repos (Zeilen "rolle=git-url").
#
# Was passiert:
#   1. Pakete und Swap
#   2. Claude Code für den Pocket-Concierge-Benutzer (offizieller Installer)
#   3. Ein Arbeitsverzeichnis pro Rolle mit inbox/, ggf. aus einem eigenen Repo
#   4. Hilfsprogramme nach /usr/local/bin
#   5. systemd-Units: eine Sitzung pro Rolle plus Inbox-Watcher

set -euo pipefail

ENV_FILE="${POCKET_CONCIERGE_ENV_FILE:-/etc/pocket-concierge/pocket-concierge.env}"
REPOS_FILE="${POCKET_CONCIERGE_REPOS_FILE:-/etc/pocket-concierge/role-repos}"
HOST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { printf '[pocket-setup] %s\n' "$*"; }
warn() { printf '[pocket-setup] WARNUNG: %s\n' "$*" >&2; }

[[ $EUID -eq 0 ]] || { echo "Bitte als root ausführen (sudo)." >&2; exit 1; }
[[ -r $ENV_FILE ]] || { echo "Konfiguration fehlt: $ENV_FILE" >&2; exit 1; }

# shellcheck source=/dev/null
source "$ENV_FILE"
: "${POCKET_CONCIERGE_USER:?POCKET_CONCIERGE_USER fehlt in $ENV_FILE}"
: "${POCKET_CONCIERGE_ROLES:?POCKET_CONCIERGE_ROLES fehlt in $ENV_FILE}"
SWAP_GB="${POCKET_CONCIERGE_SWAP_GB:-2}"

id "$POCKET_CONCIERGE_USER" >/dev/null 2>&1 || { echo "Benutzer $POCKET_CONCIERGE_USER existiert nicht." >&2; exit 1; }
USER_HOME="$(getent passwd "$POCKET_CONCIERGE_USER" | cut -d: -f6)"
ROLES_DIR="$USER_HOME/roles"

as_user() { sudo -u "$POCKET_CONCIERGE_USER" -H "$@"; }

# --- 1. Pakete und Swap -------------------------------------------------------
log "Pakete"
export DEBIAN_FRONTEND=noninteractive
missing=()
for pkg in git tmux inotify-tools curl jq; do
  dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done
if ((${#missing[@]})); then
  apt-get update -qq
  apt-get install -y -qq "${missing[@]}"
fi

if [[ $SWAP_GB -gt 0 ]] && ! swapon --show=NAME --noheadings | grep -q .; then
  log "Swap ${SWAP_GB} GB"
  fallocate -l "${SWAP_GB}G" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# --- 2. Claude Code -----------------------------------------------------------
if [[ -x $USER_HOME/.local/bin/claude ]]; then
  log "Claude Code ist installiert (aktualisiert sich selbst)"
else
  log "Claude Code installieren"
  as_user bash -c 'curl -fsSL https://claude.ai/install.sh | bash'
fi
# shellcheck disable=SC2016  # \$HOME soll erst in der Shell des Benutzers aufgelöst werden
as_user bash -c 'grep -q ".local/bin" ~/.profile 2>/dev/null || echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> ~/.profile'

# --- 3. Rollen ----------------------------------------------------------------
declare -A REPO_FOR=()
if [[ -r $REPOS_FILE ]]; then
  while IFS='=' read -r role url; do
    [[ -z $role || $role == \#* ]] && continue
    REPO_FOR["$role"]="$url"
  done < "$REPOS_FILE"
fi

as_user mkdir -p "$ROLES_DIR"
for role in $POCKET_CONCIERGE_ROLES; do
  [[ $role =~ ^[a-z][a-z0-9-]{0,30}$ ]] || { warn "Ungültiger Rollenname '$role', übersprungen"; continue; }
  dir="$ROLES_DIR/$role"

  if [[ ! -d $dir && -n ${REPO_FOR[$role]:-} ]]; then
    log "Rolle $role: Repo klonen"
    if ! as_user git clone --quiet "${REPO_FOR[$role]}" "$dir"; then
      warn "Klonen für $role fehlgeschlagen (Deploy-Key hinterlegt?). Leeres Verzeichnis wird angelegt; nach dem Einrichten des Keys das Verzeichnis löschen und dieses Skript erneut ausführen."
    fi
  fi

  as_user mkdir -p "$dir/inbox/done" "$dir/inbox/parked"

  if [[ ! -e $dir/CLAUDE.md ]]; then
    template="$HOST_DIR/templates/role/CLAUDE.md"
    [[ $role == concierge ]] && template="$HOST_DIR/templates/concierge/CLAUDE.md"
    log "Rolle $role: CLAUDE.md aus Vorlage"
    sed -e "s/@ROLE@/$role/g" -e "s/@ROLES@/$POCKET_CONCIERGE_ROLES/g" "$template" | as_user tee "$dir/CLAUDE.md" >/dev/null
  fi

  # Inboxen gehören nie in ein Repo.
  if [[ -d $dir/.git ]]; then
    exclude="$dir/.git/info/exclude"
    grep -qx 'inbox/' "$exclude" 2>/dev/null || echo 'inbox/' | as_user tee -a "$exclude" >/dev/null
  fi
done

# --- 4. Hilfsprogramme --------------------------------------------------------
log "Hilfsprogramme"
for tool in "$HOST_DIR"/bin/*; do
  chmod 755 "$tool"
  ln -sfn "$tool" "/usr/local/bin/$(basename "$tool")"
done

# --- 5. systemd ---------------------------------------------------------------
log "systemd-Units"
for unit in "$HOST_DIR"/systemd/*; do
  sed "s/@USER@/$POCKET_CONCIERGE_USER/g" "$unit" > "/etc/systemd/system/$(basename "$unit")"
done
systemctl daemon-reload

wanted=()
for role in $POCKET_CONCIERGE_ROLES; do wanted+=("pocket-role@$role.service"); done

# Rollen, die nicht mehr konfiguriert sind, anhalten (Daten bleiben erhalten).
while read -r unit _; do
  [[ $unit == pocket-role@*.service ]] || continue
  keep=0
  for w in "${wanted[@]}"; do [[ $w == "$unit" ]] && keep=1; done
  if ((keep == 0)); then
    log "Rolle aus Konfiguration entfernt, halte an: $unit"
    systemctl disable --now "$unit" || true
  fi
done < <(systemctl list-units --all --plain --no-legend 'pocket-role@*' 2>/dev/null)

systemctl enable --now "${wanted[@]}" pocket-watch.service
systemctl restart pocket-watch.service

log "Fertig. Rollen: $POCKET_CONCIERGE_ROLES"
cat <<EOF

Nächste Schritte (einmalig):
  1. Als $POCKET_CONCIERGE_USER einloggen und je Rolle anmelden:
       tmux -L pocket-<rolle> attach      (Abmelden vom Fenster: Strg+b, dann d)
     In der Sitzung /login ausführen und die Rückfrage für Remote Control bestätigen.
  2. In der Claude-App die Sitzung "concierge" öffnen.
  Status:  pocket-status
EOF
