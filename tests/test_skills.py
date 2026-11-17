"""The skills and guides, which this plugin shares word for word with the release edition.

The release edition (`plugins/cloudaeye/` on the `release` branch, what Anthropic's directory reads)
carries the same `skills/` and `resources/skills/` files as this plugin, except `create-owners`, which
needs this plugin's script. So these are the release edition's rules for them (its
`tests/test_release_edition.py`), checked here where the skills are written: no skill but
create-owners runs the script or pre-approves more than reading, every guide a skill reads exists, every
upload cuts the diff the same way, and no command carries what makes Claude Code ask on every run.
"""
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
READING = {"Read", "Grep", "Glob", "LS"}
OWN_SCRIPT = {"create-owners"}  # this plugin only: it runs scripts/create_owners.py on the machine
SKILLS = sorted(ROOT.glob("skills/*/SKILL.md"))
SHARED = [p for p in SKILLS if p.parent.name not in OWN_SCRIPT]
GUIDES = sorted(ROOT.glob("resources/skills/*.md"))


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    return yaml.safe_load(text.split("---\n")[1])


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_every_skill_parses_and_only_create_owners_preapproves_more_than_reading(skill):
    meta = _frontmatter(skill)
    assert meta["name"] == skill.parent.name
    for key in ("description", "when_to_use"):
        value = meta.get(key) or ""
        assert not value.endswith(("(", "(\"")), f"{skill.parent.name} {key} cut short: a # began a comment"
    if skill.parent.name in OWN_SCRIPT:
        # its own script and nothing wider: an unrestricted Bash was a policy hold in the directory's review
        assert set(meta["allowed-tools"]) <= {"Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "Read"}, meta
        return
    tools = meta.get("allowed-tools")
    if tools is not None:
        names = tools if isinstance(tools, list) else re.split(r"[,\s]+", str(tools).strip())
        assert set(n for n in names if n) <= READING, (skill.parent.name, tools)


def test_no_shared_skill_or_guide_runs_the_script_or_reads_a_credential():
    for path in [*SHARED, *GUIDES]:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        assert "scripts/cae" not in text and not re.search(r"\bcae [a-z]", text), rel
        assert "gh api" not in text and "gh auth" not in text, rel
        assert "pre-approved" not in text, rel


def test_every_guide_a_skill_reads_exists_and_every_guide_is_read():
    named = set()
    for path in [*SKILLS, *GUIDES]:
        named |= set(re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/resources/skills/([a-z0-9-]+)\.md",
                                path.read_text(encoding="utf-8")))
    guides = {p.stem for p in GUIDES}
    assert named <= guides, f"named but missing: {sorted(named - guides)}"
    assert guides <= named, f"never read: {sorted(guides - named)}"


def test_every_upload_command_cuts_the_diff_the_same_way():
    """Twelve skills carry the same command; one drifting would review a different diff."""
    lines = []
    for path in [*SKILLS, ROOT / "resources" / "skills" / "no-target-branch.md"]:
        lines += [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
                  if "X-Upload-Token" in ln and ln.strip().startswith(("git -c credential.helper=", "mkdir -p .cloudaeye"))]
    assert len(lines) == 13
    for line in lines:
        assert "xargs -I{} cp -p {} .cloudaeye/index && export GIT_INDEX_FILE=.cloudaeye/index && git add -N ." in line
        assert "| curl -sS --fail-with-body -K .cloudaeye/upload.curl -F 'base_sha=<-' -F 'file=@.cloudaeye/session.diff'" in line
        assert "--output=.cloudaeye/session.diff" in line


def test_no_command_carries_what_keeps_claude_code_asking():
    """A `>` redirection, a leading `cd`, `: ` anywhere, or a token or id on curl's own line each turn
    Claude Code's "don't ask again" into asking on every run (measured 17 Nov 2026; the release
    edition's test says how)."""
    for path in [*SKILLS, *GUIDES]:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line.startswith(("cd '<TOP>'", "git ", "mkdir -p .cloudaeye")):
                continue
            rel = path.relative_to(ROOT).as_posix()
            assert not line.startswith("cd "), f"{rel}: after a cd Claude Code applies no saved rule to the writes"
            bare = re.sub(r"<[^<>]*>", "", line)
            assert ">" not in bare.replace("2>/dev/null", ""), f"{rel}: a redirection"
            found = re.search(r"(?:\| |&& )curl (-[^|&;]*)", line)
            curl = found.group(1) if found else ""
            assert ": " not in line, f"{rel}: a rule holding ': ' is never saved"
            assert "-H " not in curl and " -w " not in curl and "<" not in curl.replace("'base_sha=<-'", ""), \
                f"{rel}: curl's own arguments change from run to run"


def test_the_help_lists_exactly_the_commands_this_plugin_has():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    table = readme.split("## Commands", 1)[1].split("\n\n", 2)[1]
    listed = set(re.findall(r"^\| `/cloudaeye:([a-z-]+)` \|", table, re.M))
    assert listed == {p.parent.name for p in SKILLS}
