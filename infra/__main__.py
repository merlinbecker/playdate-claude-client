"""Pulumi-Programm für eine Pocket-Concierge-Instanz.

Standard ist ein kleiner Server bei Hetzner Cloud. Der Server wird bei
Änderungen an Cloud-Init oder Image bewusst NICHT neu gebaut, damit
Sitzungen, Inboxen und Anmeldungen erhalten bleiben. Spätere Änderungen
am Host laufen über `pocket-update` auf dem Server selbst.

Zugang nur über Tailscale: Der Server tritt beim ersten Start mit einem
Auth-Key deinem Tailnet bei, SSH läuft über Tailscale SSH. Von außen ist
kein Port für Anmeldungen offen. Notfallzugang ist die Hetzner-Konsole.

Persönliche Werte (Auth-Key und Repo-URLs in Cloud-Init, Server-Adressen)
werden als Pulumi-Secrets behandelt. So tauchen sie auch in öffentlichen
Workflow-Logs nicht im Klartext auf.
"""

from __future__ import annotations

import pulumi

import cloud_init
from settings import Settings, parse_role_repos, split_list


def load_settings() -> Settings:
    cfg = pulumi.Config("pocket-concierge")
    settings = Settings(
        tailscale_auth_key=cfg.require("tailscaleAuthKey").strip(),
        repo_url=cfg.require("repoUrl"),
    )
    settings.provider = cfg.get("provider") or settings.provider
    settings.name = cfg.get("name") or settings.name
    settings.location = cfg.get("location") or settings.location
    settings.server_type = cfg.get("serverType") or settings.server_type
    settings.image = cfg.get("image") or settings.image
    backups = cfg.get_bool("backups")
    settings.backups = settings.backups if backups is None else backups
    settings.admin_user = cfg.get("adminUser") or settings.admin_user
    settings.repo_ref = cfg.get("repoRef") or settings.repo_ref
    settings.roles = split_list(cfg.get("roles")) or settings.roles
    settings.role_repos = parse_role_repos(cfg.get("roleRepos"))
    swap = cfg.get_int("swapGb")
    settings.swap_gb = settings.swap_gb if swap is None else swap
    settings.validate()
    return settings


def deploy_hetzner(settings: Settings) -> dict:
    import pulumi_hcloud as hcloud

    labels = {"app": "pocket-concierge", "instance": settings.name}

    firewall = hcloud.Firewall(
        f"{settings.name}-fw",
        name=f"{settings.name}-fw",
        labels=labels,
        rules=[
            # Kein SSH von außen. Tailscale braucht nur ausgehende Verbindungen;
            # dieser UDP-Port erlaubt zusätzlich direkte statt umgeleitete Verbindungen.
            hcloud.FirewallRuleArgs(
                direction="in",
                protocol="udp",
                port="41641",
                source_ips=["0.0.0.0/0", "::/0"],
                description="Tailscale (direkte Verbindungen)",
            ),
            hcloud.FirewallRuleArgs(
                direction="in",
                protocol="icmp",
                source_ips=["0.0.0.0/0", "::/0"],
                description="Ping",
            ),
        ],
    )

    server = hcloud.Server(
        settings.name,
        name=settings.name,
        server_type=settings.server_type,
        image=settings.image,
        location=settings.location,
        backups=settings.backups,
        firewall_ids=[firewall.id.apply(int)],
        public_nets=[hcloud.ServerPublicNetArgs(ipv4_enabled=True, ipv6_enabled=True)],
        user_data=pulumi.Output.secret(cloud_init.render(settings)),
        labels=labels,
        opts=pulumi.ResourceOptions(ignore_changes=["user_data", "image", "ssh_keys"]),
    )

    pulumi.export("provider", "hetzner")
    pulumi.export("ipv4", pulumi.Output.secret(server.ipv4_address))
    pulumi.export("ipv6", pulumi.Output.secret(server.ipv6_address))
    pulumi.export("ssh", f"ssh {settings.admin_user}@{settings.name}  (über Tailscale)")
    pulumi.export("roles", settings.roles)
    return {"firewall": firewall, "server": server}


PROVIDERS = {"hetzner": deploy_hetzner}

settings = load_settings()
if settings.provider not in PROVIDERS:
    raise pulumi.RunError(
        f"Provider {settings.provider!r} ist noch nicht umgesetzt. Verfügbar: {', '.join(PROVIDERS)}. "
        "Siehe infra/README.md, Abschnitt „Weitere Anbieter“."
    )
resources = PROVIDERS[settings.provider](settings)
