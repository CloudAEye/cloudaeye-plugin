"""The launcher steps `test_session_scripts.py` does not cover: a pull request's settings, the
developer's login, opening the connect page, and the config and owners steps.

Each is one plain `sh scripts/cae <step> ...` call in a skill, pre-approved so the developer is
never prompted, and each has to hold up on whatever the tool answered or the machine has: a
missing `gh`, a branch name that is really an option, a page that must not open over plain HTTP.
The steps that read git run against a real repository; the two that reach outside it (the GitHub
CLI, the browser) are called in-process with those stood in for.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import cloudaeye_cli  # noqa: E402


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def cli(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / "cloudaeye_cli.py"), *args], cwd=repo, capture_output=True,
                          text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})


def body(out: subprocess.CompletedProcess) -> dict:
    """The JSON a step prints after its `settings:` line."""
    text = out.stdout
    return json.loads(text.split("settings:", 1)[1] if "settings:" in text else text)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    (root / "app.py").write_text("x = 1\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "first")
    return root


@pytest.fixture
def pushed(repo: Path, tmp_path: Path) -> Path:
    """A repository whose target branch, on its remote, allows two reviewers."""
    assert cli(repo, "config", "set", "ultrareview.max_reviewers=2").returncode == 0
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "settings")
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")
    return repo


def answer(base: str, *files: object, key_url: str = "") -> str:
    """`start_session`'s answer for a pull request, as MCP wraps it."""
    doc = {"status": "ok", "session_id": "s", "pull_request": {"number": 7, "base": base, "files": list(files)},
           "key_url": key_url, "key_token": "k" * 40}
    return json.dumps({"result": json.dumps(doc)})


# ── pr-settings: read at the target branch, never at the pull request's own ──

def test_a_pull_request_reads_its_settings_at_the_target_branch_so_it_cannot_loosen_them(pushed):
    cli(pushed, "config", "set", "ultrareview.max_reviewers=3")          # the change's own edit, not merged
    out = cli(pushed, "pr-settings", answer("main", {"path": "app.py"}, "svc/b.py"))
    got = body(out)
    assert out.returncode == 0 and got["source"] == "origin/main", out.stdout + out.stderr
    assert got["ultrareview"]["max_reviewers"] == 2


@pytest.mark.parametrize("base", ["", "--upload-pack=touch x", "main;rm -rf .", "../main", "a/../../main", "/main",
                                  "main/", "main branch"])
def test_a_target_branch_that_is_not_a_branch_name_reads_nothing(pushed, base):
    out = cli(pushed, "pr-settings", answer(base, "app.py"))
    assert out.returncode == 0 and body(out) == {"error": "the target branch is unknown"}


def test_no_answer_at_all_is_an_unknown_branch_not_a_crash(repo):
    out = cli(repo, "pr-settings", "not json")
    assert out.returncode == 0 and body(out) == {"error": "the target branch is unknown"}


def test_a_path_that_reads_as_an_option_is_dropped_and_the_key_goes_only_to_a_safe_address(monkeypatch):
    seen: list[list[str]] = []
    import cloudaeye_config

    monkeypatch.setattr(cloudaeye_config, "main", lambda argv: seen.append(argv) or 0)
    monkeypatch.delenv("CE_KEY_TOKEN", raising=False)
    cloudaeye_cli.pr_settings([answer("main", "-rf", {"filename": "a.py"}, key_url="http://example.com/key"),
                               "--review"])
    assert seen[-1] == ["effective", "--ref", "origin/main", "--", "a.py"]   # no option, no key to a plain-http host
    assert "CE_KEY_TOKEN" not in os.environ
    cloudaeye_cli.pr_settings([answer("main", "a.py", key_url="https://api.cloudaeye.com/key"), "--review"])
    assert seen[-1] == ["effective", "--ref", "origin/main", "--send-key", "https://api.cloudaeye.com/key", "--", "a.py"]
    assert os.environ["CE_KEY_TOKEN"] == "k" * 40                          # in the environment, never an argument
    cloudaeye_cli.pr_settings([answer("main", "a.py", key_url="https://api.cloudaeye.com/key")])
    assert "--send-key" not in seen[-1]                                    # only a review sends the key


# ── login: the GitHub CLI first, then a noreply commit address, else nothing ──

def _runner(gh: str | Exception, email: str):
    def run(command, **_):
        if command[0] == "gh":
            if isinstance(gh, Exception):
                raise gh
            return subprocess.CompletedProcess(command, 0, stdout=gh, stderr="")
        return subprocess.CompletedProcess(command, 0, stdout=email, stderr="")
    return run


@pytest.mark.parametrize("gh, email, login", [
    ("octocat\n", "dev@example.com", "octocat"),                                     # signed-in GitHub CLI
    (FileNotFoundError("gh"), "12345+octo-cat@users.noreply.github.com\n", "octo-cat"),  # no gh: the noreply address
    (FileNotFoundError("gh"), "octo-cat@users.noreply.github.com", "octo-cat"),      # the older noreply form
    ("", "12345+octo-cat@users.noreply.github.com", "octo-cat"),                     # gh signed out prints nothing
    ("To get started with GitHub CLI, run gh auth login", "dev@example.com", ""),   # not a login: never guessed
    (FileNotFoundError("gh"), "dev@example.com", ""),                                # an ordinary address names nobody
    (subprocess.TimeoutExpired("gh", 15), "evil;rm@users.noreply.github.com", ""),   # not a login either
])
def test_the_login_is_one_github_can_have_or_none(monkeypatch, capsys, gh, email, login):
    monkeypatch.setattr(cloudaeye_cli.subprocess, "run", _runner(gh, email))
    assert cloudaeye_cli.login([]) == 0
    assert capsys.readouterr().out.strip() == f"author={login}"


# ── open: only an address a browser may be sent to ────────────────────────────

@pytest.mark.parametrize("url", ["http://example.com/connect", "javascript:alert(1)", "file:///etc/passwd", "", "https://"])
def test_an_unsafe_connect_link_is_never_opened(monkeypatch, capsys, url):
    opened: list[str] = []
    import webbrowser

    monkeypatch.setattr(webbrowser, "open", lambda u: opened.append(u) or True)
    assert cloudaeye_cli.open_link([url]) == 1
    assert capsys.readouterr().out.strip() == "cloudaeye_error=insecure_integration_url" and opened == []


@pytest.mark.parametrize("result, line", [
    (True, "opened=yes"),
    (False, "quick_link=https://app.cloudaeye.com/connect?r=1"),          # no browser: the link to click instead
    (OSError("no display"), "quick_link=https://app.cloudaeye.com/connect?r=1"),
])
def test_the_connect_page_opens_or_the_link_is_printed_to_click(monkeypatch, capsys, result, line):
    import webbrowser

    def fake(_url):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(webbrowser, "open", fake)
    assert cloudaeye_cli.open_link(["https://app.cloudaeye.com/connect?r=1"]) == 0
    assert capsys.readouterr().out.strip() == line


def test_this_machine_may_be_opened_over_plain_http_for_a_local_server(monkeypatch, capsys):
    import webbrowser

    monkeypatch.setattr(webbrowser, "open", lambda _u: True)
    assert cloudaeye_cli.open_link(["http://127.0.0.1:8767/connect"]) == 0 and "opened=yes" in capsys.readouterr().out


# ── config-start: the repository and the settings files it already has ───────

def _github_remote(repo: Path) -> None:
    """An origin on GitHub whose default branch is known locally, so nothing goes over the network."""
    git(repo, "remote", "add", "origin", "https://github.com/acme/app.git")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")


def test_config_start_names_the_repository_and_every_settings_file(repo):
    _github_remote(repo)
    (repo / "svc").mkdir()
    assert cli(repo, "config", "set", "ultrareview.max_reviewers=2").returncode == 0
    assert cli(repo, "config", "set", "--dir", "svc", "ultrareview.limits.risk=20").returncode == 0
    lines = cli(repo, "config-start").stdout.strip().splitlines()
    found = json.loads(lines[0])
    assert found["repo_full"] == "acme/app" and found["provider"] == "github" and found["base_branch"] == "main"
    assert lines[1] == "settings_files=.cloudaeye.config svc/.cloudaeye.config"


def test_config_start_with_no_remote_and_no_files_says_so_in_two_lines(repo):
    assert cli(repo, "config-start").stdout.strip().splitlines() == ["repo=none", "settings_files="]


def test_config_start_outside_git_is_one_line(tmp_path):
    outside = tmp_path / "plain"
    outside.mkdir()
    if subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=outside, capture_output=True).returncode == 0:
        pytest.skip("the temporary directory sits inside a git repository on this machine")
    assert cli(outside, "config-start").stdout.strip() == "repo=not_git"


# ── config-file: a tool's answer goes in as a file, never as text to retype ───

def test_synced_rules_are_written_from_the_tools_own_answer(repo):
    rules = {"status": "ok", "rules": [{"id": "r12", "text": "Never log a reset token.", "paths": ["backend/"]}]}
    out = cli(repo, "config-file", "sync-rules", json.dumps({"result": json.dumps(rules)}))
    assert out.returncode == 0 and json.loads(out.stdout)["written"] is True, out.stdout + out.stderr
    text = (repo / ".cloudaeye.rules").read_text(encoding="utf-8")
    assert "## r12" in text and "Never log a reset token." in text and "`backend/`" in text


def test_nothing_to_sync_and_no_file_yet_creates_no_file(repo):
    out = cli(repo, "config-file", "sync-rules", json.dumps({"status": "ok", "rules": []}))
    assert out.returncode == 0 and json.loads(out.stdout)["written"] is False
    assert not (repo / ".cloudaeye.rules").exists()


def test_a_seed_writes_only_what_the_console_sets(repo):
    got = {"status": "ok", "source": "repository", "settings": {"ultrareview.max_reviewers": 2}}
    out = cli(repo, "config-file", "seed", json.dumps(got))
    assert out.returncode == 0 and json.loads(out.stdout)["set"] == ["ultrareview.max_reviewers"], out.stdout
    assert json.loads(cli(repo, "config", "effective").stdout)["ultrareview"] == {"max_reviewers": 2}


@pytest.mark.parametrize("args", [[], ["sync-rules"], ["merge", "{}"], ["seed", "not json"]])
def test_config_file_with_the_wrong_arguments_writes_nothing(repo, args):
    out = cli(repo, "config-file", *args)
    assert out.returncode == 1 and "error" in json.loads(out.stdout)
    assert not (repo / ".cloudaeye.rules").exists() and not (repo / ".cloudaeye.config").exists()


# ── owners: create_owners.py, as it is ────────────────────────────────────────

def test_owners_passes_its_arguments_through_unchanged(repo):
    (repo / ".OWNERS.md").write_text("# Owners\n", encoding="utf-8")
    out = cli(repo, "owners", "--collect")
    assert out.returncode == 0, out.stdout + out.stderr
    assert json.loads(out.stdout)["owners"] == {".OWNERS.md": "# Owners\n"}
    bad = cli(repo, "owners", "--team", "Cloud")
    assert bad.returncode == 1 and json.loads(bad.stdout)["error"] == "--team needs --team-lead or --member"
