import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from owners_file import contributors, create, create_all, destination


class OwnersFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        (self.root / "src").mkdir()
    def git(self, *args, env=None):
        return subprocess.check_output(["git", "-C", str(self.root), *args],
                                       env=env, stderr=subprocess.PIPE, encoding="utf-8")

    def init(self):
        self.git("init")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "commit.gpgsign", "false")

    def commit(self, path, name="Alice", email="alice@example.com", date=None):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(file.read_text() + "change\n" if file.exists() else "change\n")
        self.git("add", "--", path)
        env = {**os.environ, "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email}
        if date:
            env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        self.git("commit", "-m", "test", env=env)

    def test_local_ranking_and_directory_scope(self):
        self.init()
        self.commit("src/a", "Bob", "bob@example.com")
        self.commit("src/a")
        self.commit("src/nested/b")
        self.commit("other/c", "Other", "other@example.com")
        result = create(self.root, "src")
        self.assertEqual([p["name"] for p in result["contributors"]], ["Alice", "Bob"])
        self.assertEqual([p["ownership_percent"] for p in result["contributors"]], [66.7, 33.3])
        content = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("alice@example.com", content)
        self.assertIn("66.7% (2 lines)", content)
        self.assertIn("- Lead Maintainer: Alice <alice@example.com>\n", content)
        self.assertIn("- Team Members: Alice <alice@example.com>, Bob <bob@example.com>\n", content)
        self.assertNotIn("Suggested", content)
        self.assertNotIn("@Alice", content)

    def test_github_noreply_handles_populate_fields(self):
        self.init()
        self.commit("src/a", "Display Name", "123+alice@users.noreply.github.com")
        self.commit("src/a", "Display Name", "123+alice@users.noreply.github.com")
        self.commit("src/a", "Bob", "bob@users.noreply.github.com")
        result = create(self.root, "src")
        content = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("- Lead Maintainer: @alice\n", content)
        self.assertIn("- Team Members: @alice, @bob\n", content)
        self.assertIn("- Ownership: @alice: 66.7% (2 lines)", content)
        self.assertIn("- Contact Email: \n", content)

    def test_no_commits_creates_blank_template(self):
        self.init()
        result = create(self.root, "src")
        self.assertEqual(result["contributors"], [])
        self.assertTrue(any("no commits" in w for w in result["warnings"]))

    def test_all_directories_skip_existing_and_ignored(self):
        self.init()
        self.commit("src/nested/a")
        (self.root / "empty").mkdir()
        (self.root / "ignored").mkdir()
        (self.root / ".gitignore").write_text("ignored/\n")
        existing = self.root / "src" / "OWNERS.md"
        existing.write_text("human ownership")
        result = create_all(self.root)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(existing.read_text(), "human ownership")
        for directory in (".", "src/nested", "empty"):
            self.assertTrue((self.root / directory / "OWNERS.md").exists())
        for directory in (".git", "ignored"):
            self.assertFalse((self.root / directory / "OWNERS.md").exists())
        self.assertEqual(sum(r["status"] == "skipped" for r in result["results"]), 1)

    def test_cli_no_directory_creates_all(self):
        self.init()
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("owners_file.py"))],
            cwd=self.root / "src", capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "ok")
        self.assertTrue((self.root / "OWNERS.md").exists())
        self.assertTrue((self.root / "src" / "OWNERS.md").exists())

    def test_all_reports_partial_errors(self):
        self.init()
        original = create
        def fail_one(root, directory):
            if directory == "src":
                raise ValueError("test failure")
            return original(root, directory)
        with patch("owners_file.create", side_effect=fail_one):
            result = create_all(self.root)
        self.assertEqual(result["status"], "error")
        self.assertEqual([r["status"] for r in result["results"]], ["created", "error"])

    def test_percentages_include_contributors_outside_top_three(self):
        self.init()
        for name in ("Alice", "Bob", "Carol", "Dave"):
            self.commit("src/a", name, f"{name.lower()}@example.com")
        people, _ = contributors(self.root, "src")
        self.assertEqual(len(people), 3)
        self.assertEqual([p["ownership_percent"] for p in people], [25.0, 25.0, 25.0])

    def test_root_directory(self):
        target, directory = destination(self.root, ".")
        self.assertEqual(directory, ".")
        self.assertEqual(target, self.root / "OWNERS.md")
        self.init()
        self.commit("src/a")
        people = create(self.root, ".")["contributors"]
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0]["ownership_percent"], 100.0)

    def test_no_overwrite(self):
        existing = self.root / "src" / "OWNERS.md"
        existing.write_text("human edits", encoding="utf-8")
        with self.assertRaises(ValueError):
            create(self.root, "src")
        self.assertEqual(existing.read_text(encoding="utf-8"), "human edits")

    def test_exclusive_creation(self):
        target = self.root / "src" / "OWNERS.md"
        target.write_text("appeared during generation", encoding="utf-8")
        with patch("owners_file.destination", return_value=(target, "src")), patch(
                "owners_file.contributors", return_value=([], [])):
            with self.assertRaises(FileExistsError):
                create(self.root, "src")
        self.assertEqual(target.read_text(encoding="utf-8"), "appeared during generation")

    def test_reject_outside_directory(self):
        with self.assertRaises(ValueError):
            destination(self.root, "..")

    def test_reject_missing_directory_and_regular_file(self):
        with self.assertRaises(FileNotFoundError):
            destination(self.root, "missing")
        (self.root / "file").touch()
        with self.assertRaises(ValueError):
            destination(self.root, "file")

    def test_reject_git_metadata_and_nested_metadata(self):
        (self.root / ".git" / "worktrees" / "other").mkdir(parents=True)
        for directory in (".git", ".git/worktrees/other"):
            with self.subTest(directory=directory), self.assertRaisesRegex(ValueError, "Git metadata"):
                destination(self.root, directory)

    def test_reject_separate_git_dir_and_common_worktree_metadata(self):
        metadata = self.root / "repository-metadata"
        (metadata / "worktrees" / "linked").mkdir(parents=True)
        with patch("owners_file.subprocess.check_output", return_value=(
                f"{metadata / 'worktrees' / 'linked'}\n{metadata}\n")):
            for directory in ("repository-metadata", "repository-metadata/worktrees/linked"):
                with self.subTest(directory=directory), self.assertRaisesRegex(ValueError, "Git metadata"):
                    destination(self.root, directory)
            self.assertEqual(destination(self.root, "src")[1], "src")

    def test_metadata_lookup_failure_with_git_marker_fails_closed(self):
        (self.root / ".git").write_text("gitdir: missing\n", encoding="utf-8")
        with patch("owners_file.subprocess.check_output", side_effect=subprocess.CalledProcessError(128, "git")):
            with self.assertRaisesRegex(ValueError, "cannot verify"):
                destination(self.root, "src")

    def test_real_separate_git_directory_is_not_an_ownership_destination(self):
        metadata = self.root / "metadata"
        subprocess.run(
            ["git", "init", "--separate-git-dir", str(metadata), str(self.root)],
            check=True, capture_output=True,
        )
        with self.assertRaisesRegex(ValueError, "Git metadata"):
            destination(self.root, "metadata/objects")
        self.assertEqual(destination(self.root, "src")[1], "src")

    def test_cli_local_unicode_history_independent_of_windows_code_page(self):
        self.init()
        self.commit("src/a", "Jos\u00e9", "jose@example.com")
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("owners_file.py")), "--", "src"],
            cwd=self.root, capture_output=True,
            env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "created")
        self.assertIn("Jos\u00e9", (self.root / "src" / "OWNERS.md").read_text(encoding="utf-8"))

    def test_mailmap_and_literal_directory(self):
        self.init()
        self.commit("src[1]/a", "Alias", "alias@example.com")
        self.commit("src1/a", "Other", "other@example.com")
        (self.root / ".mailmap").write_text("Alice <alice@example.com> <alias@example.com>\n")
        people, _ = contributors(self.root, "src[1]")
        self.assertEqual([p["name"] for p in people], ["Alice"])

    def test_old_history_and_new_directory(self):
        self.init()
        self.commit("src/a", date="2000-01-01T12:00:00+0000")
        result = create(self.root, "src")
        self.assertEqual(result["contributors"][0]["lines"], 1)
        (self.root / "new").mkdir()
        self.assertEqual(create(self.root, "new")["contributors"], [])

    def test_line_share_not_commit_count_and_ignores_working_edits(self):
        self.init()
        (self.root / "src/a").write_text("one\ntwo\nthree\n")
        self.commit("src/a", "Alice", "alice@example.com", date="2000-01-01T12:00:00+0000")
        self.commit("src/a", "Bob", "bob@example.com")
        self.commit("src/a", "Bob", "bob@example.com")
        (self.root / "src/a").write_text("uncommitted replacement\n")
        (self.root / "src/untracked").write_text("not counted\n")
        result = create(self.root, "src")
        self.assertEqual([p["name"] for p in result["contributors"]], ["Alice", "Bob"])
        self.assertEqual([p["lines"] for p in result["contributors"]], [4, 2])
        self.assertEqual([p["ownership_percent"] for p in result["contributors"]], [66.7, 33.3])

    def test_binary_and_ownership_files_excluded(self):
        self.init()
        self.commit("src/a")
        (self.root / "src/image.bin").write_bytes(b"\0binary\n")
        (self.root / "src/nested").mkdir()
        (self.root / "src/nested/OWNERS.md").write_text("not counted\n")
        self.git("add", ".")
        self.git("commit", "-m", "metadata")
        people, warnings = contributors(self.root, "src")
        self.assertEqual([(p["name"], p["lines"]) for p in people], [("Alice", 1)])
        self.assertTrue(any("binary" in w for w in warnings))

    def test_shallow_warning(self):
        self.init()
        self.commit("src/a")
        (self.root / ".git" / "shallow").write_text(self.git("rev-parse", "HEAD"))
        people, warnings = contributors(self.root, "src")
        self.assertEqual(len(people), 1)
        self.assertTrue(any("Shallow" in w for w in warnings))

    def test_symlink_escape_and_existing_dangling_symlink(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        try:
            (self.root / "escape").symlink_to(outside, target_is_directory=True)
            (self.root / "src" / "OWNERS.md").symlink_to(outside / "missing")
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        with self.assertRaises(ValueError):
            destination(self.root, "escape")
        with self.assertRaises(ValueError):
            create(self.root, "src")
        self.assertFalse((outside / "missing").exists())


if __name__ == "__main__":
    unittest.main()
