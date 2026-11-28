"""Einstellungen einer Pocket-Concierge-Instanz.

Alle persönlichen Werte kommen aus der Pulumi-Konfiguration, die der
GitHub-Workflow aus Secrets und Variablen setzt. Im Repo stehen nur
Standardwerte, die für jeden passen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ROLE_NAME = re.compile(r"^[a-z][a-z0-9-]{0,30}$")


def split_list(value: str | None) -> list[str]:
    """Trennt eine Liste an Kommas, Leerzeichen oder Zeilenumbrüchen."""
    if not value:
        return []
    return [item for item in re.split(r"[\s,]+", value.strip()) if item]


def parse_role_repos(value: str | None) -> dict[str, str]:
    """Liest Zeilen der Form `rolle=git-url` (Kommentare mit # erlaubt)."""
    repos: dict[str, str] = {}
    for line in (value or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"roleRepos: Zeile ohne '=': {line!r}")
        role, url = (part.strip() for part in line.split("=", 1))
        if not ROLE_NAME.match(role):
            raise ValueError(f"roleRepos: ungültiger Rollenname {role!r}")
        if not url:
            raise ValueError(f"roleRepos: leere URL für Rolle {role!r}")
        repos[role] = url
    return repos


@dataclass
class Settings:
    tailscale_auth_key: str
    repo_url: str
    provider: str = "hetzner"
    name: str = "pocket-concierge"
    location: str = "nbg1"
    server_type: str = "cx23"
    image: str = "ubuntu-24.04"
    backups: bool = True
    admin_user: str = "pocket"
    repo_ref: str = "main"
    roles: list[str] = field(default_factory=lambda: ["concierge"])
    role_repos: dict[str, str] = field(default_factory=dict)
    swap_gb: int = 2

    def validate(self) -> None:
        if not self.tailscale_auth_key.startswith("tskey-"):
            raise ValueError("tailscaleAuthKey sieht nicht wie ein Tailscale-Auth-Key aus (tskey-…)")
        if not ROLE_NAME.match(self.name):
            raise ValueError(f"name: ungültiger Servername {self.name!r} (a-z, 0-9, -)")
        if "concierge" not in self.roles:
            raise ValueError("roles muss die Rolle 'concierge' enthalten")
        for role in self.roles:
            if not ROLE_NAME.match(role):
                raise ValueError(f"roles: ungültiger Rollenname {role!r} (a-z, 0-9, -)")
        unknown = set(self.role_repos) - set(self.roles)
        if unknown:
            raise ValueError(f"roleRepos nennt Rollen, die nicht in roles stehen: {sorted(unknown)}")
        if not ROLE_NAME.match(self.admin_user):
            raise ValueError(f"adminUser: ungültiger Benutzername {self.admin_user!r}")
        if not 0 <= self.swap_gb <= 16:
            raise ValueError("swapGb muss zwischen 0 und 16 liegen")
