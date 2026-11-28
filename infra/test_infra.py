"""Tests ohne Cloud-Konto: Einstellungen, Cloud-Init und Ressourcen mit Pulumi-Mocks.

Aufruf im Ordner infra/:  python -m pytest -q   (oder: python test_infra.py)
"""

from __future__ import annotations

import os
import sys
import unittest

import yaml

sys.path.insert(0, os.path.dirname(__file__))

import cloud_init  # noqa: E402
from settings import Settings, parse_role_repos, parse_role_types, split_list  # noqa: E402

SECRET_SIG = "1b47061264138c4ac30d75fd1eb44270"


def unwrap(value):
    """Gibt (Wert, ist_geheim) zurück; Mocks liefern Secrets als verpacktes Dict."""
    if isinstance(value, dict) and value.get("4dabf18193072939515e22adb298388d") == SECRET_SIG:
        return value["value"], True
    return value, False


KEY = "tskey-auth-kTEST123CNTRL-abcdefTestOnly"


def make_settings(**overrides) -> Settings:
    values = dict(
        tailscale_auth_key=KEY,
        repo_url="https://github.com/example/pocket-concierge",
        roles=["concierge", "wissen", "bauen"],
        role_repos={"wissen": "git@github.com:example/wissen.git"},
        role_types={"bauen": "bauen", "wissen": "wissen"},
    )
    values.update(overrides)
    return Settings(**values)


class SettingsTest(unittest.TestCase):
    def test_split_list(self):
        self.assertEqual(split_list("a, b\nc  d"), ["a", "b", "c", "d"])
        self.assertEqual(split_list(""), [])

    def test_parse_role_repos(self):
        repos = parse_role_repos("# Kommentar\nwissen = git@x:y.git\n\nbauen=https://h/z\n")
        self.assertEqual(repos, {"wissen": "git@x:y.git", "bauen": "https://h/z"})
        with self.assertRaises(ValueError):
            parse_role_repos("ohne-gleichheitszeichen")
        with self.assertRaises(ValueError):
            parse_role_repos("Gross=url")

    def test_parse_role_types(self):
        self.assertEqual(parse_role_types("bauen-a=bauen, notizen=wissen"), {"bauen-a": "bauen", "notizen": "wissen"})
        with self.assertRaises(ValueError):
            parse_role_types("x=unbekannt")

    def test_rejects_type_for_unknown_role(self):
        with self.assertRaises(ValueError):
            make_settings(role_types={"fremd": "bauen"}).validate()

    def test_valid(self):
        make_settings().validate()

    def test_rejects_bad_server_name(self):
        with self.assertRaises(ValueError):
            make_settings(name="Mein Server").validate()

    def test_rejects_repo_for_unknown_role(self):
        with self.assertRaises(ValueError):
            make_settings(role_repos={"fremd": "url"}).validate()

    def test_requires_concierge(self):
        with self.assertRaises(ValueError):
            make_settings(roles=["wissen"], role_repos={}).validate()

    def test_rejects_bad_key(self):
        with self.assertRaises(ValueError):
            make_settings(tailscale_auth_key="kein-schluessel").validate()


class CloudInitTest(unittest.TestCase):
    def test_render(self):
        text = cloud_init.render(make_settings())
        self.assertTrue(text.startswith("#cloud-config\n"))
        data = yaml.safe_load(text)
        self.assertFalse(data["ssh_pwauth"])
        self.assertTrue(data["disable_root"])
        self.assertNotIn("ssh_authorized_keys", data["users"][0])
        self.assertEqual(data["hostname"], "pocket-concierge")
        files = {f["path"]: f for f in data["write_files"]}
        self.assertEqual(files[cloud_init.TAILSCALE_KEY_PATH]["permissions"], "0600")
        self.assertEqual(files[cloud_init.TAILSCALE_KEY_PATH]["content"].strip(), KEY)
        env = files[cloud_init.ENV_PATH]["content"]
        self.assertIn("POCKET_CONCIERGE_ROLES='concierge wissen bauen'", env)
        self.assertIn("POCKET_CONCIERGE_ROLE_TYPES='bauen=bauen wissen=wissen'", env)
        self.assertEqual(files[cloud_init.ROLE_REPOS_PATH]["permissions"], "0600")
        self.assertIn("wissen=git@github.com:example/wissen.git", files[cloud_init.ROLE_REPOS_PATH]["content"])
        self.assertEqual(data["runcmd"][-1], ["bash", "/opt/pocket-concierge/host/setup-host.sh"])

    def test_no_role_repos_file_when_empty(self):
        data = yaml.safe_load(cloud_init.render(make_settings(role_repos={})))
        self.assertNotIn(cloud_init.ROLE_REPOS_PATH, [f["path"] for f in data["write_files"]])

    def test_env_quotes_values(self):
        env = cloud_init.render_env(make_settings(repo_url="https://x/y z"))
        self.assertIn("POCKET_CONCIERGE_REPO_URL='https://x/y z'", env)


class ProgramTest(unittest.TestCase):
    """Führt __main__.py mit gemockter Pulumi-Laufzeit aus."""

    checked = False

    def test_resources(self):
        import pulumi

        @pulumi.runtime.test
        def run():
            return self._run_program()

        run()
        self.assertTrue(self.checked, "Prüfungen wurden nicht ausgeführt")

    def _run_program(self):
        import pulumi

        created: list[tuple[str, dict]] = []

        class Mocks(pulumi.runtime.Mocks):
            def new_resource(self, args: pulumi.runtime.MockResourceArgs):
                created.append((args.typ, dict(args.inputs)))
                outputs = dict(args.inputs)
                if args.typ == "hcloud:index/server:Server":
                    outputs.update(ipv4Address="198.51.100.10", ipv6Address="2001:db8::1")
                return [f"{args.name}-id" if args.typ != "hcloud:index/firewall:Firewall" else "42", outputs]

            def call(self, args: pulumi.runtime.MockCallArgs):
                return {}

        pulumi.runtime.set_mocks(
            Mocks(),
            project="pocket-concierge-infra",
            stack="test",
            preview=False,
        )
        pulumi.runtime.set_all_config(
            {
                "pocket-concierge:tailscaleAuthKey": KEY,
                "pocket-concierge:repoUrl": "https://github.com/example/pocket-concierge",
                "pocket-concierge:roles": "concierge,wissen",
            }
        )

        import importlib

        sys.modules.pop("__main__infra", None)
        spec = importlib.util.spec_from_file_location("__main__infra", os.path.join(os.path.dirname(__file__), "__main__.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        def check(_):
            types = [typ for typ, _ in created]
            self.assertNotIn("hcloud:index/sshKey:SshKey", types)
            self.assertIn("hcloud:index/firewall:Firewall", types)
            self.assertIn("hcloud:index/server:Server", types)
            server = next(inputs for typ, inputs in created if typ == "hcloud:index/server:Server")
            self.assertEqual(server["serverType"], "cx23")
            self.assertEqual(server["location"], "nbg1")
            self.assertTrue(server["backups"])
            raw_user_data, user_data_secret = unwrap(server["userData"])
            self.assertTrue(user_data_secret, "userData muss geheim sein")
            self.assertNotIn("sshKeys", {k for k, v in server.items() if v})
            user_data = yaml.safe_load(raw_user_data)
            env = next(f["content"] for f in user_data["write_files"] if f["path"] == cloud_init.ENV_PATH)
            self.assertIn("POCKET_CONCIERGE_ROLES='concierge wissen'", env)
            firewall = next(inputs for typ, inputs in created if typ == "hcloud:index/firewall:Firewall")
            rules, _ = unwrap(firewall["rules"])
            self.assertFalse(
                any(rule.get("protocol") == "tcp" and rule.get("port") == "22" for rule in rules),
                "SSH darf von außen nicht offen sein",
            )
            self.assertTrue(any(rule.get("port") == "41641" for rule in rules), "Tailscale-Port fehlt")
            self.checked = True

        res = module.resources
        return pulumi.Output.all(res["firewall"].urn, res["server"].urn).apply(check)


if __name__ == "__main__":
    unittest.main()
