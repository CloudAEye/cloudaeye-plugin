"""Cursor packaging reuses the shared skills and OAuth server configuration."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CursorPluginTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(
            (ROOT / ".cursor-plugin" / "plugin.json").read_text(encoding="utf-8")
        )

    def test_manifest_paths_are_existing_components_inside_plugin(self):
        self.assertEqual(self.manifest["name"], "cloudaeye")
        for field in ("skills", "rules", "mcpServers"):
            with self.subTest(field=field):
                relative_path = self.manifest[field]
                self.assertTrue(relative_path.startswith("./"))
                path = (ROOT / relative_path).resolve()
                self.assertTrue(path.is_relative_to(ROOT))
                self.assertTrue(path.exists())

    def test_skills_are_shared_instead_of_copied(self):
        skills = (ROOT / self.manifest["skills"]).resolve()
        self.assertEqual(skills, ROOT / "skills")
        self.assertTrue((skills / "describe" / "SKILL.md").is_file())
        self.assertTrue((ROOT / "scripts" / "repository_preflight.py").is_file())

    def test_cursor_bridge_keeps_oauth_and_uses_hosted_mcp(self):
        path = ROOT / self.manifest["mcpServers"]
        self.assertEqual(path.resolve(), ROOT / "cursor" / "mcp.json")
        config = json.loads(path.read_text(encoding="utf-8"))
        server = config["mcpServers"]["cloudaeye"]
        self.assertEqual(server["type"], "stdio")
        self.assertEqual(server["command"], "npx")
        self.assertIn("mcp-remote@0.14.3", server["args"])
        self.assertIn("https://api.cloudaeye.com/mcp", server["args"])
        self.assertNotIn("--allow-http", server["args"])
        self.assertIn("http-only", server["args"])
        self.assertIn("--static-oauth-client-metadata", server["args"])
        self.assertNotIn("headers", server)

    def test_bridge_registers_public_native_client_without_fixed_redirect(self):
        metadata = json.loads(
            (ROOT / "cursor" / "oauth-client-metadata.json").read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["application_type"], "native")
        self.assertEqual(metadata["token_endpoint_auth_method"], "none")
        self.assertIn("mcp:tools", metadata["scope"].split())
        self.assertNotIn("redirect_uris", metadata)
        self.assertNotIn("client_secret", metadata)

    def test_other_clients_keep_direct_http_config(self):
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["cloudaeye"]
        self.assertEqual(server["type"], "http")
        self.assertEqual(server["url"], "${CLOUDAEYE_URL:-https://api.cloudaeye.com/mcp}")

    def test_marketplace_points_to_this_plugin(self):
        catalog = json.loads(
            (ROOT / ".cursor-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        entry = catalog["plugins"][0]
        self.assertEqual(entry["name"], self.manifest["name"])
        self.assertEqual((ROOT / entry["source"]).resolve(), ROOT)

    def test_cursor_guidance_handles_shared_skill_aliases_and_script_root(self):
        rule = (ROOT / "cursor" / "rules" / "cloudaeye-compatibility.mdc").read_text(
            encoding="utf-8"
        )
        self.assertIn("alwaysApply: true", rule)
        self.assertIn("actually available tool", rule)
        self.assertIn("CLAUDE_PLUGIN_ROOT", rule)
        self.assertIn("CURSOR_PLUGIN_ROOT", rule)
        self.assertIn("get_job_result", rule)
        self.assertIn("explicit approvals", rule)

    def test_claude_manifest_is_preserved(self):
        manifest = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], self.manifest["name"])
        self.assertEqual(manifest["version"], self.manifest["version"])

    @unittest.skipUnless(shutil.which("powershell"), "Windows PowerShell is required")
    def test_installer_copies_release_files_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            command = [
                "powershell", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File",
                str(ROOT / "scripts" / "install_cursor_plugin.ps1"),
                "-DestinationRoot", temp,
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = Path(temp) / "cloudaeye"
            for relative in (
                ".cursor-plugin/plugin.json", ".mcp.json", "README.md",
                "cursor/mcp.json", "cursor/oauth-client-metadata.json",
                "cursor/rules/cloudaeye-compatibility.mdc",
                "skills/review/SKILL.md", "skills/create-owners/SKILL.md",
                "scripts/repository_preflight.py", "scripts/owners_file.py",
            ):
                self.assertEqual(
                    (installed / relative).read_bytes(), (ROOT / relative).read_bytes()
                )
            for relative in (
                ".claude", "skills/assign-reviewer", "skills/OWNERS.md",
                "scripts/__pycache__", "scripts/test_cursor_plugin.py",
            ):
                self.assertFalse((installed / relative).exists(), relative)
            repeated = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("Existing Cursor plugin was not modified", repeated.stderr)


if __name__ == "__main__":
    unittest.main()
