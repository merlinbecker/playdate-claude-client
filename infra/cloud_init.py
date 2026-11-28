"""Erzeugt die Cloud-Init-Konfiguration für den ersten Start des Servers.

Cloud-Init legt nur das Nötigste an: Benutzer, SSH-Härtung, Konfiguration
unter /etc/arborist und den Klon dieses Repos. Alles Weitere erledigt
host/setup-host.sh, das sich später jederzeit erneut ausführen lässt.
"""

from __future__ import annotations

import shlex

import yaml

from settings import Settings

ENV_PATH = "/etc/arborist/arborist.env"
ROLE_REPOS_PATH = "/etc/arborist/role-repos"
CHECKOUT = "/opt/arborist"


class _Dumper(yaml.SafeDumper):
    """Schreibt mehrzeilige Texte als lesbaren Block (|)."""


def _str(dumper: yaml.SafeDumper, value: str):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str)


def render_env(settings: Settings) -> str:
    values = {
        "ARBORIST_USER": settings.admin_user,
        "ARBORIST_ROLES": " ".join(settings.roles),
        "ARBORIST_REPO_URL": settings.repo_url,
        "ARBORIST_REPO_REF": settings.repo_ref,
        "ARBORIST_SWAP_GB": str(settings.swap_gb),
    }
    lines = ["# Von Pulumi erzeugt. Änderungen hier überschreibt kein späteres Deployment."]
    lines += [f"{key}={shlex.quote(value)}" for key, value in values.items()]
    return "\n".join(lines) + "\n"


def render_role_repos(settings: Settings) -> str:
    return "".join(f"{role}={url}\n" for role, url in sorted(settings.role_repos.items()))


def render(settings: Settings) -> str:
    write_files = [
        {"path": ENV_PATH, "permissions": "0644", "owner": "root:root", "content": render_env(settings)},
    ]
    if settings.role_repos:
        write_files.append(
            {
                "path": ROLE_REPOS_PATH,
                "permissions": "0600",
                "owner": "root:root",
                "content": render_role_repos(settings),
            }
        )

    config = {
        "users": [
            {
                "name": settings.admin_user,
                "groups": ["sudo"],
                "shell": "/bin/bash",
                "sudo": "ALL=(ALL) NOPASSWD:ALL",
                "lock_passwd": True,
                "ssh_authorized_keys": [settings.ssh_public_key],
            }
        ],
        "disable_root": True,
        "ssh_pwauth": False,
        "package_update": True,
        "package_upgrade": True,
        "packages": ["git", "tmux", "inotify-tools", "curl", "jq", "unattended-upgrades"],
        "write_files": write_files,
        "runcmd": [
            ["git", "clone", "--branch", settings.repo_ref, settings.repo_url, CHECKOUT],
            ["bash", f"{CHECKOUT}/host/setup-host.sh"],
        ],
    }
    return "#cloud-config\n" + yaml.dump(config, Dumper=_Dumper, sort_keys=False, allow_unicode=True)
