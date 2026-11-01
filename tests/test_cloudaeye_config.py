"""The settings files: what applies to a change, and what never does.

Run with `python -m pytest tests` from the plugin's root; needs git.

What would go wrong silently: settings read from nowhere turning into values (a review that
looks configured and is not); a directory's settings reaching a sibling directory or the
whole repository; a nested "paths never reviewed" pattern that git quietly ignores; a pull
request loosening its own limits; and a sync that drops a rule the team wrote.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "cloudaeye_config.py"


def ce(root, *args, stdin=None):
    got = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args],
                         input=stdin, capture_output=True, text=True, encoding="utf-8")
    return got


def ce_json(root, *args, stdin=None):
    got = ce(root, *args, stdin=stdin)
    return json.loads(got.stdout)


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def write(root, path, text="x\n"):
    p = Path(root) / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    for f in ("src/a.py", "docs/guide/b.md", "services/payments/api/c.py", "services/search/d.py"):
        write(root, f)
    return root


CHANGE_SETTINGS = ("ultrareview", "review", "control_flow", "triage")


# ── no files anywhere: CloudAEye's defaults and no rules ─────────────────────

def test_with_no_settings_file_anywhere_nothing_is_set_and_there_are_no_rules(repo):
    for changed in ([], ["src/a.py"], ["docs/guide/b.md", "services/payments/api/c.py"]):
        out = ce_json(repo, "effective", "--", *changed)
        assert not any(k in out for k in CHANGE_SETTINGS), out
        assert out["rules"] == [] and out["files"] == [] and out["applied"] == [] and out["problems"] == []
    assert ce(repo, "skip").stdout == ""


def test_the_template_with_every_setting_commented_out_is_still_the_defaults(repo):
    template = (SCRIPT.parent.parent / "resources" / "config")
    write(repo, ".cloudaeye.config", (template / "config.md").read_text(encoding="utf-8"))
    write(repo, ".cloudaeye.rules", (template / "rules.md").read_text(encoding="utf-8"))
    out = ce_json(repo, "effective", "--", "src/a.py")
    assert not any(k in out for k in CHANGE_SETTINGS), out
    assert out["rules"] == [] and out["problems"] == []


def test_with_no_files_on_the_target_branch_a_pull_request_gets_the_defaults(repo, tmp_path):
    origin = tmp_path / "origin.git"
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "init")
    git(tmp_path, "init", "-q", "--bare", str(origin))
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")
    out = ce_json(repo, "effective", "--ref", "origin/main", "--", "src/a.py")
    assert not any(k in out for k in CHANGE_SETTINGS) and out["rules"] == []


# ── a file covers its own directory and everything below, nothing else ───────

def test_a_directory_file_applies_to_its_directory_and_below_and_never_to_a_sibling(repo):
    assert ce_json(repo, "set", "--dir", "services/payments", "ultrareview.limits.risk=20",
                   "ultrareview.max_reviewers=2")["file"] == "services/payments/.cloudaeye.config"

    deep = ce_json(repo, "effective", "--", "services/payments/api/c.py")
    assert deep["ultrareview"] == {"limits": {"risk": 20}, "max_reviewers": 2}
    assert deep["applied"] == ["services/payments/.cloudaeye.config"]

    for elsewhere in ("services/search/d.py", "src/a.py", "README.md"):
        out = ce_json(repo, "effective", "--", elsewhere)
        assert "ultrareview" not in out and out["applied"] == [], elsewhere


def test_the_nearest_file_wins_setting_by_setting_and_instructions_add_up(repo):
    ce(repo, "set", "ultrareview.limits.risk=40", "ultrareview.limits.slop=50")
    ce(repo, "add", "ultrareview.instructions", "Always one human for migrations.")
    ce(repo, "set", "--dir", "services/payments", "ultrareview.limits.risk=20")
    ce(repo, "add", "--dir", "services/payments", "ultrareview.instructions", "Payments need two humans.")

    out = ce_json(repo, "effective", "--", "services/payments/api/c.py")
    assert out["ultrareview"]["limits"] == {"risk": 20, "slop": 50}      # risk from below, slop from the root
    assert out["ultrareview"]["instructions"] == ["Always one human for migrations.", "Payments need two humans."]
    assert ce_json(repo, "effective", "--", "src/a.py")["ultrareview"] == {
        "limits": {"risk": 40, "slop": 50}, "instructions": ["Always one human for migrations."]}


def test_across_a_change_the_value_that_asks_for_more_review_wins(repo):
    ce(repo, "set", "ultrareview.limits.risk=40", "ultrareview.max_reviewers=1", "control_flow.effort=low")
    ce(repo, "set", "--dir", "docs", "ultrareview.limits.risk=80", "ultrareview.checks.architecture=off")
    ce(repo, "set", "--dir", "services/payments", "ultrareview.max_reviewers=3", "ultrareview.limits.severity=low",
       "control_flow.effort=high")

    docs_only = ce_json(repo, "effective", "--", "docs/guide/b.md")
    assert docs_only["ultrareview"]["limits"]["risk"] == 80
    assert docs_only["ultrareview"]["checks"] == {"architecture": False}

    both = ce_json(repo, "effective", "--", "docs/guide/b.md", "services/payments/api/c.py")
    assert both["ultrareview"]["limits"] == {"risk": 40, "severity": "low"}
    assert both["ultrareview"]["max_reviewers"] == 3
    assert both["control_flow"]["effort"] == "high"
    assert "checks" not in both["ultrareview"], "a check stays on unless every changed file's settings turn it off"


def test_triage_reads_the_top_level_file_only(repo):
    assert "error" in ce_json(repo, "set", "--dir", "docs", "triage.okrs=`docs/okrs.md`")
    ce(repo, "set", "triage.okrs=`docs/okrs.md`")
    assert ce_json(repo, "effective", "--", "docs/guide/b.md")["triage"] == {"okrs": "`docs/okrs.md`"}


def test_a_comment_beside_a_setting_survives_setting_it_and_commenting_it_out(repo):
    ce(repo, "set", "ultrareview.checks.review=off")
    text = (repo / ".cloudaeye.config").read_text(encoding="utf-8")
    assert "- Review: off <!-- bugs and security -->" in text
    ce(repo, "set", "ultrareview.checks.review=-")
    text = (repo / ".cloudaeye.config").read_text(encoding="utf-8")
    assert "<!-- - Review: off --> <!-- bugs and security -->" in text
    assert "ultrareview" not in ce_json(repo, "effective"), "commented out again: the default"


def test_a_directory_rule_covers_that_directory_and_below_only(repo):
    ce(repo, "add-rule", "--dir", "services/payments", "--heading", "Money", "--text", "Amounts are Decimal.")
    ce(repo, "add-rule", "--dir", "services/payments", "--heading", "Auth", "--text", "Routes check auth.",
       "--paths", "api/")
    ce(repo, "add-rule", "--heading", "Logs", "--text", "No request bodies in logs.")
    rules = ce_json(repo, "effective", "--", "src/a.py")["rules"]
    by_text = {r["text"]: r["paths"] for r in rules}
    assert by_text == {
        "No request bodies in logs.": [],                          # the root file: every file
        "Amounts are Decimal.": ["services/payments/"],            # its directory and below
        "Routes check auth.": ["services/payments/api/"],          # "Applies to" is relative to it
    }
    assert "error" in ce_json(repo, "add-rule", "--dir", "docs", "--heading", "x", "--text", "y",
                              "--paths", "../src")


def test_a_nested_skip_pattern_leaves_out_its_directory_and_below_as_git_reads_it(repo):
    for f in ("services/payments/fixtures/f.json", "services/payments/api/fixtures/g.json",
              "services/search/fixtures/h.json", "generated/top.py", "src/generated/deep.py"):
        write(repo, f)
    ce(repo, "add", "--dir", "services/payments", "review.skip", "**/fixtures/")
    ce(repo, "add", "review.skip", "**/generated/**")
    git(repo, "add", "--intent-to-add", ".")

    specs = [s for s in ce(repo, "skip").stdout.splitlines() if s]
    left = subprocess.run(["git", "-C", str(repo), "diff", "--name-only", "--", ".",
                           *[f":(exclude){s}" for s in specs]],
                          capture_output=True, text=True, check=True).stdout.split()
    assert "services/payments/fixtures/f.json" not in left       # the directory itself
    assert "services/payments/api/fixtures/g.json" not in left   # and below
    assert "services/search/fixtures/h.json" in left             # never a sibling
    assert "generated/top.py" not in left and "src/generated/deep.py" not in left
    assert "src/a.py" in left


# ── a pull request reads the target branch ───────────────────────────────────

def test_a_pull_request_cannot_loosen_its_own_settings(repo, tmp_path):
    origin = tmp_path / "origin.git"
    ce(repo, "set", "ultrareview.limits.risk=40")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "init")
    git(tmp_path, "init", "-q", "--bare", str(origin))
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")
    git(repo, "checkout", "-q", "-b", "feature")
    ce(repo, "set", "ultrareview.limits.risk=95")
    git(repo, "commit", "-qam", "loosen")

    pr = ce_json(repo, "effective", "--ref", "origin/main", "--", ".cloudaeye.config", "src/a.py")
    assert pr["ultrareview"]["limits"]["risk"] == 40
    assert pr["pending"] == [".cloudaeye.config"]
    assert ce_json(repo, "effective", "--", "src/a.py")["ultrareview"]["limits"]["risk"] == 95


# ── the sync ─────────────────────────────────────────────────────────────────

def test_the_sync_creates_no_file_when_there_is_nothing_to_sync(repo):
    out = ce_json(repo, "sync-rules", "--file", "-", stdin=json.dumps({"status": "ok", "rules": []}))
    assert out["written"] is False and not (repo / ".cloudaeye.rules").exists()


def test_the_sync_replaces_its_own_rules_and_keeps_the_teams(repo):
    ce(repo, "add-rule", "--heading", "Ours", "--text", "Our own rule.")
    first = {"status": "ok", "rules": [{"id": "r2", "text": "Say why.", "paths": []},
                                       {"id": "r7", "text": "ORM only.", "paths": ["src/db/"]}]}
    assert ce_json(repo, "sync-rules", "--file", "-", stdin=json.dumps(first))["added"] == ["r2", "r7"]
    second = {"status": "ok", "rules": [{"id": "r7", "text": "ORM only, no raw SQL.", "paths": ["src/db/"]}]}
    out = ce_json(repo, "sync-rules", "--file", "-", stdin=json.dumps(second))
    assert out["removed"] == ["r2"] and out["yours"] == 1
    texts = {r["text"] for r in ce_json(repo, "effective")["rules"]}
    assert texts == {"ORM only, no raw SQL.", "Our own rule."}
    # an organisation that removed every rule: the synced ones go, the team's stay
    ce(repo, "sync-rules", "--file", "-", stdin=json.dumps({"status": "ok", "rules": []}))
    assert {r["text"] for r in ce_json(repo, "effective")["rules"]} == {"Our own rule."}
