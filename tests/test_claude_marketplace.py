"""claude-marketplace/ is the release edition, what Anthropic's directory reads: it must pass the rules
the directory applies to an organisation it has not verified, which `claude plugin validate` does not check.

Each rule is the portal's own refusal, reworded (17 Nov 2026): only Markdown, text, JSON, YAML
and images; no file starting with #!; `allowed-tools` no wider than Read, Grep, Glob and LS; an
MCP server at a fixed public address. And what the rewrite must not lose: every guide a skill
points to exists, no skill still runs the plugin's script, and the commands the help prints are
the commands there are.
"""
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
EDITION = ROOT / "claude-marketplace"
ALLOWED_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}
ALLOWED_NAMES = {"LICENSE", "README", ".gitignore"}
ALLOWED_TOOLS = {"Read", "Grep", "Glob", "LS"}
SKILLS = sorted(EDITION.glob("skills/*/SKILL.md"))


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    return yaml.safe_load(text.split("---\n")[1])


def test_the_edition_holds_only_the_file_types_the_directory_accepts():
    for path in EDITION.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(EDITION).as_posix()
        assert path.suffix.lower() in ALLOWED_SUFFIXES or path.name in ALLOWED_NAMES, rel
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}:
            continue
        raw = path.read_bytes()
        assert not raw.startswith(b"#!"), f"{rel} starts with #!"
        assert b"\0" not in raw, f"{rel} holds a NUL byte"
        raw.decode("utf-8")
        assert b"\r\n" not in raw, f"{rel} has Windows line endings"
    assert not (EDITION / ".claude" / "skills").exists()
    assert sorted(p.name for p in (EDITION / ".claude-plugin").iterdir()) == ["icon.png", "plugin.json"]


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_every_skill_parses_and_preapproves_nothing_beyond_reading(skill):
    meta = _frontmatter(skill)
    assert meta["name"] == skill.parent.name
    tools = meta.get("allowed-tools")
    if tools is not None:
        names = tools if isinstance(tools, list) else re.split(r"[,\s]+", str(tools).strip())
        assert set(n for n in names if n) <= ALLOWED_TOOLS, (skill.parent.name, tools)
    for key in ("description", "when_to_use"):
        value = meta.get(key) or ""
        assert not value.endswith(("(", "(\"")), f"{skill.parent.name} {key} cut short: a # began a comment"


def test_the_mcp_server_is_at_a_fixed_public_address():
    servers = json.loads((EDITION / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    assert list(servers) == ["cloudaeye"]
    url = servers["cloudaeye"]["url"]
    assert url == "https://api.cloudaeye.com/mcp" and url.isascii()
    manifest = json.loads((EDITION / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert "${" not in json.dumps(manifest)
    # The one setting is the developer's own LLM key, as the directory advises for a credential:
    # sensitive (the system's credential store), and used only as a header on the connection here.
    options = manifest.get("userConfig") or {}
    assert list(options) == ["llm_api_key"] and options["llm_api_key"]["sensitive"] is True
    assert options["llm_api_key"].get("default") == "", "an unset key arrives empty, never as its placeholder"
    assert servers["cloudaeye"].get("headers") == {"X-CloudAEye-LLM-Key": "${user_config.llm_api_key}"}


def test_no_skill_or_guide_runs_the_plugins_script_or_reads_a_credential():
    for path in [*SKILLS, *EDITION.glob("resources/**/*.md")]:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(EDITION).as_posix()
        assert "scripts/cae" not in text and not re.search(r"\bcae (start|upload|guide|report|preflight)\b", text), rel
        assert "gh api" not in text and "gh auth" not in text, rel
        assert "pre-approved" not in text, rel


def test_every_guide_a_skill_reads_exists_and_every_guide_is_read():
    named = set()
    for path in [*SKILLS, *EDITION.glob("resources/**/*.md")]:
        named |= set(re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/resources/skills/([a-z0-9-]+)\.md", path.read_text(encoding="utf-8")))
    guides = {p.stem for p in EDITION.glob("resources/skills/*.md")}
    assert named <= guides, f"named but missing: {sorted(named - guides)}"
    assert guides <= named, f"never read: {sorted(guides - named)}"


def test_every_upload_command_cuts_the_diff_the_same_way():
    """Twelve skills carry the same command; one drifting would review a different diff."""
    lines = []
    for path in [*SKILLS, EDITION / "resources" / "skills" / "no-target-branch.md"]:
        lines += [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
                  if "X-Upload-Token" in ln and ln.strip().startswith(("git -c credential.helper=", "mkdir -p .cloudaeye"))
                  and "blame" not in ln]     # create-owners uploads a blame, not a diff
    assert len(lines) == 13
    for line in lines:
        assert "xargs -I{} cp -p {} .cloudaeye/index && export GIT_INDEX_FILE=.cloudaeye/index && git add -N ." in line
        assert "| curl -sS --fail-with-body -K .cloudaeye/upload.curl -F 'base_sha=<-' -F 'file=@.cloudaeye/session.diff'" in line
        assert "--output=.cloudaeye/session.diff" in line


def test_no_command_carries_what_keeps_claude_code_asking():
    """Measured on 17 Nov 2026 by answering Claude Code's permission prompts as "don't ask again" across
    two sessions: a `>` redirection is a file edit no Bash rule covers; a `cd` in front stops saved
    rules applying to the writes after it; `: ` anywhere on the line makes a rule unsaveable; a token,
    job or session id there makes the rule exact. Each turns "don't ask again" into asking on every
    run, so the address and token go through a curl config file (`printf ... | tee`, then `curl -K`).
    With all of it, the upload line is asked on the first two runs and never again, in any session."""
    for path in [*SKILLS, *EDITION.glob("resources/skills/*.md")]:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line.startswith(("cd '<TOP>'", "git ", "mkdir -p .cloudaeye")):
                continue
            rel = path.relative_to(EDITION).as_posix()
            assert not line.startswith("cd "), f"{rel}: after a cd Claude Code applies no saved rule to the writes"
            bare = re.sub(r"<[^<>]*>", "", line)                       # the placeholders a skill fills in
            assert ">" not in bare.replace("2>/dev/null", ""), f"{rel}: a redirection"
            found = re.search(r"(?:\| |&& )curl (-[^|&;]*)", line)       # the command, not upload.curl
            curl = found.group(1) if found else ""
            assert ": " not in line, f"{rel}: a rule holding ': ' is never saved"
            assert "-H " not in curl and " -w " not in curl and "<" not in curl.replace("'base_sha=<-'", ""), \
                f"{rel}: curl's own arguments change from run to run"


def test_the_help_lists_exactly_the_commands_this_edition_has():
    readme = (EDITION / "README.md").read_text(encoding="utf-8")
    table = readme.split("## Commands", 1)[1].split("\n\n", 2)[1]
    listed = set(re.findall(r"^\| `/cloudaeye:([a-z-]+)` \|", table, re.M))
    assert listed == {p.parent.name for p in SKILLS}


def test_nothing_reads_as_curl_piped_into_a_program():
    """The portal warns `RUNTIME_FETCH_EXEC` ("download-and-execute", shown to reviewers and users as an
    install-time risk) when the word `curl` is followed by a `|` within some characters, across lines: a
    Markdown table after an upload command was enough. Validated three times on 18 Nov 2026: flagged with a
    pipe 307 characters or less after a `curl`, never at 342 or more. And no line names curl, even as a
    file name, before a pipe into a shell (create-owners' `| xargs … sh -c` after `upload.curl`)."""
    for path in EDITION.rglob("*"):
        if path.suffix.lower() not in {".md", ".txt", ".json", ".yaml", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(EDITION).as_posix()
        for found in re.finditer(r"(?:^|[\s`(])curl\b", text, re.M):
            pipe = text.find("|", found.end())
            line = text.count("\n", 0, found.end()) + 1
            assert pipe < 0 or pipe - found.end() >= 342, f"{rel}:{line}"
        for number, line in enumerate(text.splitlines(), 1):
            shell = re.search(r"\b(sh|bash|zsh) -c\b|\|\s*(sh|bash|zsh)\b", line)
            assert not (shell and "curl" in line), f"{rel}:{number}: a shell and curl on one line"


def test_a_skill_names_curl_only_inside_its_commands():
    """What was left flagged on 18 Nov 2026 after the pipes were gone: review-arch's prose said "each
    shell step is the one plain `git` or `curl` command shown, and Claude Code asks before the first
    run", and create-owners ran `sh -c` and curl in one command (now two). The ten skills cleared once
    their prose stopped naming curl ("before `curl` runs", "`curl: (22)` and an error"), so the prose
    of a skill or guide never does; the commands in its ```bash blocks may."""
    for path in [*SKILLS, *EDITION.glob("resources/skills/*.md")]:
        prose = re.sub(r"```bash\n.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        assert not re.search(r"\bcurl\b", prose), path.relative_to(EDITION).as_posix()


def test_both_editions_have_the_same_commands():
    """The main edition (the repository root, run by the helper scripts) and this one word their skills
    differently, so a change to a skill is made in both. What they offer must not drift: a command in one
    and not the other is a command one set of users cannot run."""
    mains = {p.parent.name for p in ROOT.glob("skills/*/SKILL.md")}
    assert {p.parent.name for p in SKILLS} == mains


def test_claude_code_never_loads_this_folder_as_part_of_the_main_edition():
    """CloudAEye's own marketplace installs the repository root, this folder included; Claude Code reads a
    plugin's skills only from its own skills/ folder, so these never show as a second set of commands."""
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert [p["source"] for p in marketplace["plugins"]] == ["./"]
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert "claude-marketplace" not in json.dumps(manifest)
