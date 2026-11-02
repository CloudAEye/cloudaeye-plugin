"""The settings files: what applies to a change, and what never does.

Run with `python -m pytest tests` from the plugin's root; needs git.

What would go wrong silently: settings read from nowhere turning into values (a review that
looks configured and is not); a directory's settings reaching a sibling directory or the
whole repository; a nested "paths never reviewed" pattern that git quietly ignores; a pull
request loosening its own limits; and a sync that drops a rule the team wrote.
"""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "cloudaeye_config.py"
_spec = importlib.util.spec_from_file_location("cloudaeye_config", SCRIPT)
CFG = sys.modules["cloudaeye_config"] = importlib.util.module_from_spec(_spec)   # dataclasses look it up
_spec.loader.exec_module(CFG)


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


def test_assigning_human_review_is_off_only_when_every_changed_files_settings_say_so(repo):
    ce(repo, "set", "--dir", "docs", "ultrareview.assign_reviewers=false")
    assert "- Auto-assign human reviewer: false" in (repo / "docs" / ".cloudaeye.config").read_text(encoding="utf-8")
    assert ce_json(repo, "effective", "--", "docs/guide/b.md")["ultrareview"] == {"assign_reviewers": False}
    both = ce_json(repo, "effective", "--", "docs/guide/b.md", "src/a.py")
    assert "ultrareview" not in both, "true is the default; one file still wanting a reviewer keeps it"
    assert "error" in ce_json(repo, "set", "ultrareview.assign_reviewers=maybe")


def test_triage_reads_the_top_level_file_only(repo):
    assert "error" in ce_json(repo, "set", "--dir", "docs", "triage.okrs=`docs/okrs.md`")
    ce(repo, "set", "triage.okrs=`docs/okrs.md`")
    assert ce_json(repo, "effective", "--", "docs/guide/b.md")["triage"] == {"okrs": "`docs/okrs.md`"}


def _line(repo, start, d=""):
    text = (repo / d / ".cloudaeye.config").read_text(encoding="utf-8")
    return next(ln for ln in text.splitlines() if ln.startswith(start))


def test_the_options_beside_a_setting_survive_setting_it_and_commenting_it_out_and_stay_lined_up(repo):
    ce(repo, "set", "ultrareview.checks.security=off")
    column = _line(repo, "<!-- - Bugs:").index("<!-- true")
    line = _line(repo, "- Security:")
    assert line.startswith("- Security: false ") and line.endswith("<!-- true | false. Includes leaked secrets -->")
    assert line.index("<!-- true") == column, "the options stay in their column"
    ce(repo, "set", "ultrareview.checks.security=-")
    line = _line(repo, "<!-- - Security:")
    assert line.startswith("<!-- - Security: false -->") and line.index("<!-- true") == column
    assert "ultrareview" not in ce_json(repo, "effective"), "commented out again: the default"


def test_a_yes_or_no_setting_is_written_true_or_false_and_older_words_still_read(repo):
    ce(repo, "set", "ultrareview.checks.bugs=off", "control_flow.cross_repo=no", "ultrareview.assign_reviewers=False")
    assert _line(repo, "- Bugs:").startswith("- Bugs: false")
    assert _line(repo, "- Across repositories:").startswith("- Across repositories: false")
    assert _line(repo, "- Auto-assign human reviewer:").startswith("- Auto-assign human reviewer: false")
    out = ce_json(repo, "effective")
    assert out["ultrareview"]["checks"] == {"bugs": False} and out["control_flow"] == {"cross_repo": False}
    write(repo, ".cloudaeye.config", "## Control flow\n- Across repositories: yes\n## Ultrareview\n### Checks\n"
                                     "- Bugs: on\n- Security: TRUE\n")
    out = ce_json(repo, "effective")
    assert out["control_flow"] == {"cross_repo": True} and out["ultrareview"]["checks"] == {"bugs": True,
                                                                                            "security": True}
    assert out["problems"] == []
    assert "true or false" in ce_json(repo, "set", "ultrareview.checks.bugs=maybe")["error"]


PARAGRAPH = ("Changes under `services/payments/` always need two humans. Pull requests from the Platform team "
             "need one reviewer from outside the team, e.g. from Security.")


def test_the_instructions_are_one_paragraph_carried_on_indented_lines(repo):
    write(repo, ".cloudaeye.config",
          "## Ultrareview\n### Human review policy\n- Max human reviewers to assign: 2\n"
          "- Instructions: Changes under `services/payments/` always need two humans. Pull requests\n"
          "  from the Platform team need one reviewer from outside the team, e.g. from Security.\n"
          "  <!-- plain words -->\n"
          "- Auto-assign human reviewer: true\n")
    out = ce_json(repo, "effective")
    assert out["ultrareview"]["instructions"] == [PARAGRAPH], "read whole, never split on its dots"
    assert out["ultrareview"]["max_reviewers"] == 2 and out["ultrareview"]["assign_reviewers"] is True
    assert out["problems"] == []


def test_set_add_and_clear_rewrite_the_paragraph_in_place(repo):
    ce(repo, "set", f"ultrareview.instructions={PARAGRAPH}")
    lines = (repo / ".cloudaeye.config").read_text(encoding="utf-8").splitlines()
    start = lines.index(next(ln for ln in lines if ln.startswith("- Instructions:")))
    assert lines[start + 1].startswith("  ") and all(len(ln) <= 96 for ln in lines[start:start + 3]), \
        "wrapped onto indented lines, to be read"
    assert ce_json(repo, "effective")["ultrareview"]["instructions"] == [PARAGRAPH]
    ce(repo, "add", "ultrareview.instructions", "Always one human for migrations.")
    assert ce_json(repo, "effective")["ultrareview"]["instructions"] == [PARAGRAPH + " Always one human for migrations."]
    ce(repo, "set", "ultrareview.instructions=Two humans for payments.")
    assert ce_json(repo, "effective")["ultrareview"]["instructions"] == ["Two humans for payments."]
    text = (repo / ".cloudaeye.config").read_text(encoding="utf-8")
    assert blank(text).count("- Instructions:") == 1 and "Platform" not in blank(text), "replaced, never kept twice"
    ce(repo, "clear", "ultrareview.instructions")
    assert "ultrareview" not in ce_json(repo, "effective")
    assert "comment marks" in ce_json(repo, "set", "ultrareview.instructions=a --> b")["error"]
    assert "at most 2000" in ce_json(repo, "set", "ultrareview.instructions=" + "x " * 1100)["error"]


def blank(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def test_the_llm_is_read_from_the_top_level_file_only_and_the_key_never_goes_in_it(repo):
    out = ce_json(repo, "set", "review.llm=Your Own", "review.provider=OpenAI", "review.model=`gpt-6.1-terra`",
                  "review.invert_model=false")
    assert out["values"]["review"] == {"llm": "your own", "provider": "openai", "model": "gpt-6.1-terra",
                                       "invert_model": False}
    assert ce_json(repo, "effective", "--", "docs/guide/b.md")["review"] == out["values"]["review"]
    assert "top-level" in ce_json(repo, "set", "--dir", "docs", "review.model=other")["error"]
    write(repo, "docs/.cloudaeye.config", "## Review\n### LLM\n- Model: other\n")
    got = ce_json(repo, "effective", "--", "docs/guide/b.md")
    assert got["review"]["model"] == "gpt-6.1-terra"
    assert any("Model is read from the repository's top-level" in p for p in got["problems"])
    assert "not one name" in ce_json(repo, "set", "review.model=two words")["error"]
    assert "not one of" in ce_json(repo, "set", "review.provider=somewhere")["error"]


def test_with_cloudaeyes_models_a_provider_is_left_out_and_said(repo):
    ce(repo, "set", "review.llm=cloudaeye", "review.provider=azure", "review.model=gpt-6.1-terra")
    out = ce_json(repo, "effective")
    assert out["review"] == {"llm": "CloudAEye", "model": "gpt-6.1-terra"}
    assert any("Provider is for your own LLM only" in p for p in out["problems"])


def test_the_template_lists_every_setting_commented_out_with_its_options_beside_it(repo):
    template = (ROOT / "resources" / "config" / "config.md").read_text(encoding="utf-8")
    for s in CFG.SETTINGS:
        if s.kind in ("list", "paragraph"):
            assert f"<!-- - {s.label}:" in template, s.key
            continue
        line = next((ln for ln in template.splitlines() if ln.startswith(f"<!-- - {s.label}:")
                     and CFG._find_line(template.split("\n"), s, *CFG._block(template.split("\n"), s))
                     == template.split("\n").index(ln)), None)
        assert line and re.search(r"-->\s+<!-- \S", line), f"{s.key}: commented out, its options beside it"
    assert "API key" in template and "Never put an API key here" in template
    assert ce_json(repo, "effective")["rules"] == [] and "review" not in ce_json(repo, "effective")


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


# ── files people edit by hand ────────────────────────────────────────────────

def test_a_byte_order_mark_and_windows_line_endings_read_like_any_file(repo, tmp_path):
    """Notepad saves UTF-8 with a byte-order mark, which hid the first heading and with it the file."""
    (repo / ".cloudaeye.config").write_bytes(
        b"\xef\xbb\xbf## Ultrareview\r\n\r\n### Limits\r\n- Risk score: 40 / 100\r\n\r\n"
        b"### Checks\r\n- Security: OFF <!-- true | false -->\r\n")
    (repo / "docs" / ".cloudaeye.rules").write_bytes(b"\xef\xbb\xbf## r5\r\nSynced rule.\r\n")
    for ref in ("", "base"):
        if ref:
            git(repo, "add", "-A")
            git(repo, "-c", "core.autocrlf=false", "commit", "-qm", "crlf")
            git(repo, "branch", "-q", "base")
        out = ce_json(repo, "effective", *(["--ref", ref] if ref else []))
        assert out["ultrareview"] == {"limits": {"risk": 40}, "checks": {"security": False}}, ref
        assert out["rules"] == [{"id": "r5", "text": "Synced rule.", "paths": ["docs/"]}], ref
        assert out["problems"] == [], ref


def test_a_setting_written_twice_is_said_and_the_last_one_used(repo):
    write(repo, ".cloudaeye.config", "## Ultrareview\n### Limits\n- Risk score: 40\n- Risk score: 30\n")
    out = ce_json(repo, "effective")
    assert out["ultrareview"]["limits"]["risk"] == 30
    assert out["problems"] == [".cloudaeye.config line 4: Risk score is also set on line 3; line 4 is used"]


def test_a_mistake_costs_its_line_and_is_named(repo):
    write(repo, ".cloudaeye.config", "## Ultrareview\n### Limits\n- Risk scroe: 10\n- Review severity: high\n"
                                     "- AI slop score: 50\n## Somewhere\n- Foo: bar\n")
    out = ce_json(repo, "effective")
    assert out["ultrareview"] == {"limits": {"slop": 50}}
    assert len(out["problems"]) == 3
    assert "error" in ce_json(repo, "set", "ultrareview.limits.risk=140")
    assert "error" in ce_json(repo, "add", "review.skip", "../outside")


def test_show_in_a_directory_says_what_it_inherits_and_leaves_triage_to_the_root(repo):
    ce(repo, "set", "ultrareview.limits.risk=40", "triage.okrs=x")
    ce(repo, "set", "--dir", "docs", "ultrareview.limits.slop=30")
    out = ce_json(repo, "show", "--dir", "./docs/")
    assert out["file"] == "docs/.cloudaeye.config" and out["exists"] and out["elsewhere"] == [".cloudaeye.config"]
    rows = {r["key"]: r for r in out["settings"]}
    assert rows["ultrareview.limits.risk"]["value"] is None and rows["ultrareview.limits.risk"]["inherited"] == 40
    assert rows["ultrareview.limits.risk"]["inherited_from"] == "the root"
    assert rows["ultrareview.limits.slop"]["value"] == 30
    assert not any(k.startswith("triage.") for k in rows)
    assert "error" in ce_json(repo, "show", "--dir", "nowhere")


def test_clearing_a_list_and_a_sync_that_is_not_the_tools_answer(repo):
    ce(repo, "add", "review.skip", "vendor/")
    ce(repo, "add", "ultrareview.instructions", "Two humans for payments.")
    assert "review" not in ce_json(repo, "clear", "review.skip")["values"]
    assert ce_json(repo, "effective")["ultrareview"]["instructions"] == ["Two humans for payments."]
    assert "not the review_rules tool's JSON" in ce_json(repo, "sync-rules", "--file", "-", stdin="not json")["error"]
    assert "setup_required" in ce_json(repo, "sync-rules", "--file", "-",
                                       stdin=json.dumps({"status": "error", "error": "setup_required"}))["error"]


# ── what people read ─────────────────────────────────────────────────────────

def test_a_directory_file_offers_no_triage_section_and_the_template_claims_nothing_false(repo):
    ce(repo, "set", "--dir", "docs", "ultrareview.max_reviewers=3")
    text = (repo / "docs" / ".cloudaeye.config").read_text(encoding="utf-8")
    assert text.startswith("# CloudAEye settings: docs/")
    assert "Triage" not in text, "triage reads the root file only"
    assert "### LLM" not in text and "### Paths never reviewed" in text, "so does the LLM"
    ce(repo, "set", "ultrareview.max_reviewers=2")
    root_text = (repo / ".cloudaeye.config").read_text(encoding="utf-8")
    assert "## Triage PRs" in root_text and "### LLM" in root_text
    assert "Every command posts" not in root_text, "the reviews and describe post nothing"


def test_show_says_what_a_setting_is_when_no_file_names_it_and_never_a_limit_number(repo):
    rows = {r["key"]: r for r in ce_json(repo, "show")["settings"]}
    assert rows["ultrareview.checks.bugs"]["default"] == rows["ultrareview.checks.security"]["default"] == "true"
    assert rows["ultrareview.checks.bugs"]["options"] == ["true", "false"]
    assert rows["ultrareview.assign_reviewers"]["default"] == "true"
    assert rows["control_flow.effort"]["default"] == "medium"
    assert rows["control_flow.cross_repo"]["options"] == ["true", "false"]
    assert rows["ultrareview.instructions"]["default"] == "none"
    assert rows["review.llm"]["options"] == ["CloudAEye", "your own"]
    assert rows["review.model"]["default"] == "the console's setting"
    for limit in ("ultrareview.limits.risk", "ultrareview.limits.slop", "ultrareview.limits.severity"):
        assert rows[limit]["default"] == "CloudAEye's own check", "how that check is built is never printed"


def test_a_mistyped_setting_name_suggests_the_real_one(repo):
    write(repo, ".cloudaeye.config", "## Ultrareview\n### Limits\n- Risk: 40\n### Human review policy\n"
                                     "- Max reviewers: 2\n")
    problems = ce_json(repo, "effective")["problems"]
    assert problems[0].endswith("did you mean 'Risk score'?")
    assert problems[1].endswith("did you mean 'Max human reviewers to assign'?")
