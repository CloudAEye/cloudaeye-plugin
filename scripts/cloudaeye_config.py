#!/usr/bin/env python3
"""Read and write CloudAEye's settings files in a repository: .cloudaeye.config and .cloudaeye.rules.

A pair can sit in any directory and covers that directory and everything below it:
  <repo>/.cloudaeye.config, .cloudaeye.rules        the whole repository; most teams need only these
  <repo>/services/payments/.cloudaeye.config, ...   services/payments/ and below; wins over the files
                                                    above it, setting by setting

Both are markdown. A new file starts from the plugin's template (resources/config/), where every
setting is commented out with its options beside it.

Which settings apply to a change: each changed file takes the nearest value of each setting,
walking up to the root; instructions (a paragraph a file), paths never reviewed and rules add up on
the way. Across its files the change takes whatever asks for more review: the lowest limit, the
most reviewers, the lowest severity floor, a check left true unless every file's settings make it
false. The LLM and triage read the root file only. Before a commit the files are read from the
working tree; on a pull request from its target branch (--ref), so a pull request cannot change its
own settings. A yes-or-no setting is written true or false.

Commands, each printing JSON (skip prints lines):
  effective [--ref REF] [--files F|-] [--send-key URL] [-- PATH...]
                                          the settings and rules that apply to a change; with --send-key,
                                          the file's API key goes to that address and is never printed
  skip                                    every directory's paths never reviewed, as git pathspecs, one per line
  show [--dir D]                          D's settings: options, its value, what it inherits
  set [--dir D] KEY=VALUE...              write values; VALUE "-" comments the setting out again
                                          (the instructions: takes them out)
  add [--dir D] KEY TEXT                  add a path to skip, or a sentence to the end of the instructions
  clear [--dir D] KEY                     remove every path to skip, or the instructions
  rules [--dir D]                         the rules in D's .cloudaeye.rules
  sync-rules --file F|-                   your organisation's rules (review_rules' answer) into the root file
  seed --file F|-                         the console's ultrareview settings (ultrareview_settings' answer)
                                          into the root file
  add-rule [--dir D] --heading H --text T [--paths P,Q]   a rule of your own

Runs locally with Python and git; the only network call is fetching the target branch for --ref.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

CONFIG = ".cloudaeye.config"
RULES = ".cloudaeye.rules"
TEMPLATES = {CONFIG: "config.md", RULES: "rules.md"}
ON = {"on", "true", "yes"}
OFF = {"off", "false", "no"}


@dataclass(frozen=True)
class Setting:
    key: str
    section: str
    group: str            # the ### heading it sits under; "" for a section with none
    label: str            # the text before ":"
    kind: str             # bool | choice | score | number | name | text | list | paragraph
    options: tuple = ()
    lo: int = 0
    hi: int = 0


PROVIDERS = ("openai", "anthropic", "azure", "aws_bedrock", "gcp_vertex", "groq", "deepseek")
SETTINGS = (
    Setting("ultrareview.checks.checklist", "Ultrareview", "Checks", "PR checklist", "bool"),
    Setting("ultrareview.checks.bugs", "Ultrareview", "Checks", "Bugs", "bool"),
    Setting("ultrareview.checks.security", "Ultrareview", "Checks", "Security", "bool"),
    Setting("ultrareview.checks.slop", "Ultrareview", "Checks", "AI slop score", "bool"),
    Setting("ultrareview.checks.risk", "Ultrareview", "Checks", "Risk score", "bool"),
    Setting("ultrareview.checks.architecture", "Ultrareview", "Checks", "Architecture", "bool"),
    Setting("ultrareview.checks.control_flow", "Ultrareview", "Checks", "Control flow", "bool"),
    Setting("ultrareview.checks.task", "Ultrareview", "Checks", "Task check", "bool"),
    Setting("ultrareview.limits.risk", "Ultrareview", "Limits", "Risk score", "score"),
    Setting("ultrareview.limits.slop", "Ultrareview", "Limits", "AI slop score", "score"),
    Setting("ultrareview.limits.severity", "Ultrareview", "Limits", "Review severity", "choice", ("medium", "low")),
    Setting("ultrareview.assign_reviewers", "Ultrareview", "Human review policy", "Auto-assign human reviewer",
            "bool"),
    Setting("ultrareview.max_reviewers", "Ultrareview", "Human review policy", "Max human reviewers to assign",
            "choice", ("1", "2", "3")),
    Setting("ultrareview.instructions", "Ultrareview", "Human review policy", "Instructions", "paragraph"),
    Setting("review.severity_floor", "Review", "Severity floor", "Severity floor", "choice",
            ("all", "critical", "high", "medium", "low")),
    Setting("review.llm", "Review", "LLM", "LLM", "choice", ("CloudAEye", "your own")),
    Setting("review.provider", "Review", "LLM", "Provider", "choice", PROVIDERS),
    Setting("review.model", "Review", "LLM", "Model", "name"),
    Setting("review.invert_model", "Review", "LLM", "Model inversion", "bool"),
    Setting("review.api_key", "Review", "LLM", "API key", "secret"),
    Setting("review.skip", "Review", "Paths never reviewed", "Skip", "list"),
    Setting("control_flow.effort", "Control flow", "", "Effort", "choice", ("low", "medium", "high")),
    Setting("control_flow.cross_repo", "Control flow", "", "Across repositories", "bool"),
    Setting("triage.okrs", "Triage PRs", "", "OKRs", "text"),
)
BY_KEY = {s.key: s for s in SETTINGS}
#: read from the repository's top-level file only: one review runs on one model, and triage spans
#: the repository
LLM_KEYS = frozenset({"review.llm", "review.provider", "review.model", "review.invert_model", "review.api_key"})
#: the instructions are sent as written, one paragraph a file; the server reads no more than this
MAX_PARAGRAPH = 2000
#: the providers whose whole credential is one key; the others keep theirs in the console
KEY_PROVIDERS = ("openai", "anthropic", "deepseek")
#: an API key is written as the key, or as an environment variable that holds it ($NAME or ${NAME})
_ENV_REF = re.compile(r"^\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?$")
_KEY_SHAPE = re.compile(r"^[\x21-\x7e]{8,1024}$")
KEY_HEADER = "X-Key-Token"


def root_only(key: str) -> bool:
    return key.startswith("triage.") or key in LLM_KEYS
#: across a change's files, the value that asks for more review
_LOWEST = {"ultrareview.limits.risk", "ultrareview.limits.slop", "ultrareview.limits.severity",
           "review.severity_floor"}
_HIGHEST = {"ultrareview.max_reviewers", "control_flow.effort"}
_ORDER = {"ultrareview.limits.severity": ("low", "medium"),
          "review.severity_floor": ("all", "low", "medium", "high", "critical"),
          "control_flow.effort": ("low", "medium", "high")}
_RULE_ID = re.compile(r"^r\d+$", re.I)
_TICKS = re.compile(r"`([^`]+)`")
_BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")


class ConfigError(Exception):
    pass


# ── the repository ───────────────────────────────────────────────────────────

def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, env=env)


def repo_root(given: str) -> Path:
    if given:
        return Path(given).resolve()
    got = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if got.returncode != 0:
        raise ConfigError("this is not a git repository: the settings files live in one")
    return Path(got.stdout.decode("utf-8").strip())


def norm_dir(root: Path, raw: str) -> str:
    """``raw`` as a directory relative to the root, ``""`` for the root itself."""
    d = (raw or "").strip().strip("`").replace("\\", "/")
    while d.startswith("./"):
        d = d[2:]
    d = d.strip("/") if d not in ("", ".") else ""
    if raw and (raw.strip().startswith(("/", "~")) or re.match(r"^[A-Za-z]:", raw.strip())):
        raise ConfigError(f"{raw!r} is not a path inside the repository")
    if any(part == ".." for part in d.split("/")):
        raise ConfigError(f"{raw!r} is not a path inside the repository")
    if d and not (root / d).is_dir():
        raise ConfigError(f"there is no directory {d}/ in the repository")
    return d


def _dir_of(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _ancestors(directory: str) -> list[str]:
    """The root first, then each directory down to ``directory``."""
    out = [""]
    parts = [p for p in directory.split("/") if p]
    for i in range(len(parts)):
        out.append("/".join(parts[:i + 1]))
    return out


def _under(directory: str, path: str) -> str:
    """``path`` (relative to ``directory``) relative to the root."""
    p = path.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if not p or p.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", p) or ".." in p.split("/"):
        raise ConfigError(f"{path!r} is not a path inside this directory")
    return f"{directory}/{p}" if directory else p


class Files:
    """Every settings file in the repository: ``{directory: {name: text}}``."""

    def __init__(self, root: Path, ref: str = ""):
        self.root, self.ref = root, ref
        self.found: dict[str, dict[str, str]] = {}
        self.problems: list[str] = []
        names = self._list()
        for path in names:
            text = self._read(path)
            if text is not None:
                self.found.setdefault(_dir_of(path), {})[path.rsplit("/", 1)[-1]] = text

    def _list(self) -> list[str]:
        if self.ref:
            got = _git(self.root, "ls-tree", "-r", "-z", "--name-only", self.ref)
            if got.returncode != 0:
                raise ConfigError(f"{self.ref} could not be read")
            paths = got.stdout.decode("utf-8", "replace").split("\0")
        else:
            got = _git(self.root, "ls-files", "-co", "--exclude-standard", "-z", "--",
                       f":(glob)**/{CONFIG}", f":(glob)**/{RULES}")
            paths = got.stdout.decode("utf-8", "replace").split("\0") if got.returncode == 0 else []
            for name in (CONFIG, RULES):                # a repository with no commit yet
                if (self.root / name).is_file() and name not in paths:
                    paths.append(name)
        return sorted(p for p in paths if p and p.rsplit("/", 1)[-1] in (CONFIG, RULES))

    def _read(self, path: str) -> str | None:
        if self.ref:
            got = _git(self.root, "show", f"{self.ref}:{path}")
            # a byte-order mark or Windows line endings committed with the file read like any other
            return got.stdout.decode("utf-8-sig", "replace").replace("\r\n", "\n") if got.returncode == 0 else None
        try:
            return (self.root / path).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            self.problems.append(f"{path} could not be read ({type(exc).__name__})")
            return None

    def text(self, directory: str, name: str) -> str | None:
        return self.found.get(directory, {}).get(name)

    def paths(self) -> list[str]:
        return [f"{d}/{n}" if d else n for d in sorted(self.found) for n in sorted(self.found[d])]


def fetch(root: Path, ref: str) -> bool:
    """Bring ``origin/<branch>`` up to date, best effort: an old copy still reads."""
    if not ref.startswith("origin/"):
        return False
    branch = ref[len("origin/"):]
    if not _BRANCH.match(branch) or branch.startswith("-"):
        raise ConfigError(f"{branch!r} is not a branch name")
    return _git(root, "-c", "credential.helper=", "fetch", "-q", "origin", branch).returncode == 0


# ── reading markdown with comments ───────────────────────────────────────────

def blank_comments(text: str) -> str:
    """The text with every HTML comment's characters blanked, newlines kept, so line numbers hold."""
    return re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


def _headings(lines: list[str]) -> list[tuple[int, str, str]]:
    """``(line index, level, title)`` for every heading outside a comment."""
    out = []
    for i, line in enumerate(lines):
        m = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
        if m:
            out.append((i, m.group(1), m.group(2).strip()))
    return out


def _find(section: str, group: str, label: str) -> Setting | None:
    for s in SETTINGS:
        if s.section.lower() == section.lower() and s.group.lower() == group.lower() \
                and s.label.lower() == label.lower():
            return s
    matches = [s for s in SETTINGS if s.section.lower() == section.lower() and s.label.lower() == label.lower()]
    return matches[0] if len(matches) == 1 else None


def _nearest(section: str, label: str) -> str:
    """`` — did you mean 'Risk score'?`` for a label one typo away from a setting in this section."""
    import difflib

    names = sorted({s.label for s in SETTINGS if s.label and s.section.lower() == section.lower()})
    close = difflib.get_close_matches(label, names, n=1, cutoff=0.6) or [
        n for n in names if n.lower().startswith(label.lower()) or label.lower().startswith(n.lower())][:1]
    return f" — did you mean '{close[0]}'?" if close else ""


def value_of(s: Setting, raw: str):
    """The value as the other skills use it, or ``ConfigError`` naming the options."""
    text = raw.strip()
    low = text.lower()
    if s.kind == "bool":
        if low in ON:                  # on/yes as well: a file written before true/false still reads
            return True
        if low in OFF:
            return False
        raise ConfigError(f"{s.label}: {text!r} is not true or false")
    if s.kind == "choice":
        hit = next((o for o in s.options if o.lower() == low), None)
        if hit is None:
            raise ConfigError(f"{s.label}: {text!r} is not one of {' | '.join(s.options)}")
        return int(hit) if hit.isdigit() else hit
    if s.kind == "secret":
        # Never repeated in a message: the value may be the key itself.
        key = text.strip("`").strip().strip("\"'")
        if not (_ENV_REF.match(key) or _KEY_SHAPE.match(key)) or key.startswith("<!--"):
            raise ConfigError(f"{s.label}: not a key, nor an environment variable like $OPENAI_API_KEY")
        return key
    if s.kind == "name":
        name = text.strip("`").strip()
        if not name or any(c.isspace() for c in name):
            raise ConfigError(f"{s.label}: {text!r} is not one name, like gpt-6.1-terra")
        return name
    if s.kind == "paragraph":
        words = " ".join(text.split())
        if not words:
            raise ConfigError(f"{s.label}: no text")
        if "<!--" in words or "-->" in words:
            raise ConfigError(f"{s.label}: the text holds comment marks (<!-- or -->)")
        if len(words) > MAX_PARAGRAPH:
            raise ConfigError(f"{s.label}: {len(words)} characters; CloudAEye reads at most {MAX_PARAGRAPH}")
        return words
    if s.kind == "score":
        m = re.match(r"^(\d{1,3})(?:\s*/\s*100)?$", text)
        if not m or not 0 <= int(m.group(1)) <= 100:
            raise ConfigError(f"{s.label}: {text!r} is not a score from 0 to 100, like 40/100")
        return int(m.group(1))
    if s.kind == "number":
        if not text.isdigit() or not s.lo <= int(text) <= s.hi:
            raise ConfigError(f"{s.label}: {text!r} is not a number from {s.lo} to {s.hi}")
        return int(text)
    if s.kind == "list":
        items = _TICKS.findall(text) or [text]
        return [i.strip() for i in items if i.strip()]
    if not text:
        raise ConfigError(f"{s.label}: no value")
    return text


def _continuation(lines: list[str], i: int) -> int:
    """The index past a paragraph setting's lines: the indented lines under it, up to a blank line,
    the next item or a heading. ``lines`` has its comments blanked."""
    j = i + 1
    while j < len(lines) and lines[j].strip() and lines[j][:1].isspace() \
            and not re.match(r"^\s*-\s", lines[j]) and not re.match(r"^\s*#", lines[j]):
        j += 1
    return j


def parse_config(text: str, source: str = CONFIG) -> tuple[dict, list[str]]:
    """``({key: value}, problems)`` for every setting written outside a comment."""
    values: dict = {}
    problems: list[str] = []
    seen: dict[str, int] = {}
    section = group = ""
    lines = blank_comments(text.lstrip("﻿")).split("\n")
    i = 0
    while i < len(lines):
        line, n = lines[i], i + 1
        i += 1
        m = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
        if m:
            if m.group(1) == "##":
                section, group = m.group(2).strip(), ""
            else:
                group = m.group(2).strip()
            continue
        item = re.match(r"^\s*-\s+(.*\S)\s*$", line)
        if not item:
            continue
        kv = re.match(r"^([^:]+?)\s*:\s*(.*)$", item.group(1))
        setting = _find(section, group, kv.group(1)) if kv else None
        if setting is not None and setting.kind == "paragraph":
            end = _continuation(lines, n - 1)
            raw = " ".join([kv.group(2)] + [ln.strip() for ln in lines[n:end]])
            i = end
            try:
                value = value_of(setting, raw)
            except ConfigError as exc:
                problems.append(f"{source} line {n}: {exc}; it was left out")
                continue
            if setting.key in seen:
                problems.append(f"{source} line {n}: {setting.label} are also written on line "
                                f"{seen[setting.key]}; line {n} is used")
            seen[setting.key] = n
            values[setting.key] = value
            continue
        if setting is None:
            hint = _nearest(section, kv.group(1)) if kv else ""
            # the label only: a key written on the wrong line must not be repeated
            what = repr(kv.group(1)) if kv else "it"
            problems.append(f"{source} line {n}: {what} is not a setting here, so it was skipped{hint}")
            continue
        try:
            value = value_of(setting, kv.group(2))
        except ConfigError as exc:
            problems.append(f"{source} line {n}: {exc}; the default stands")
            continue
        if setting.kind == "list":
            values.setdefault(setting.key, []).extend(value)
        else:
            if setting.key in seen:
                problems.append(f"{source} line {n}: {setting.label} is also set on line {seen[setting.key]}; "
                                f"line {n} is used")
            seen[setting.key] = n
            values[setting.key] = value
    return values, problems


def key_source(value: str) -> str:
    """Where an API key setting takes its key from, in words that never hold the key."""
    m = _ENV_REF.match(value or "")
    return f"${m.group(1)}" if m else "written in the file"


def resolve_key(value: str) -> str:
    """The key itself: the environment variable's value, or what the file holds. Never printed."""
    m = _ENV_REF.match(value or "")
    return os.environ.get(m.group(1), "").strip() if m else value


def masked(values: dict) -> dict:
    """``values`` safe to print: an API key becomes where it comes from."""
    if "review.api_key" not in values:
        return values
    return {**values, "review.api_key": key_source(values["review.api_key"])}


def send_key(url: str, token: str, key: str) -> tuple[bool, str]:
    """Send the key to CloudAEye's key route for this session. ``(sent, why not)``; the key is never echoed."""
    import urllib.error
    import urllib.request

    if not re.match(r"^(https://|http://(localhost|127\.0\.0\.1)(:\d+)?/)", url or ""):
        return False, "the key address is not HTTPS"
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", token or ""):
        return False, "the session's key token is missing"
    request = urllib.request.Request(url, data=json.dumps({"api_key": key}).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", KEY_HEADER: token})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status == 200, "" if response.status == 200 else f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        try:
            why = json.loads(exc.read().decode("utf-8")).get("error") or ""
        except ValueError:
            why = ""
        return False, f"HTTP {exc.code}" + (f": {why}" if why else "")
    except (urllib.error.URLError, OSError) as exc:
        return False, f"CloudAEye could not be reached ({type(exc).__name__})"


def nest(values: dict) -> dict:
    out: dict = {}
    for key, value in values.items():
        node = out
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return out


# ── which settings apply ─────────────────────────────────────────────────────

class Settings:
    """Every ``.cloudaeye.config`` and ``.cloudaeye.rules`` of one repository, parsed."""

    def __init__(self, files: Files):
        self.files = files
        self.configs: dict[str, dict] = {}
        self.problems = list(files.problems)
        for directory in sorted(files.found):
            text = files.text(directory, CONFIG)
            if text is not None:
                source = f"{directory}/{CONFIG}" if directory else CONFIG
                values, found = parse_config(text, source)
                self.configs[directory] = values
                self.problems += found
                for key in sorted(k for k in values if directory and root_only(k)):
                    self.problems.append(f"{source}: {BY_KEY[key].label} is read from the repository's "
                                         f"top-level {CONFIG} only, so it was skipped")

    def chain(self, directory: str, upto: bool = True) -> tuple[dict, dict]:
        """``(values, where)`` in force in ``directory``: the nearest file wins, instructions add up.

        ``upto=False`` stops above ``directory``: what a file there would inherit."""
        values: dict = {}
        where: dict = {}
        dirs = _ancestors(directory)
        for d in dirs if upto else dirs[:-1]:
            for key, value in self.configs.get(d, {}).items():
                if key == "review.skip" or root_only(key):
                    continue
                if key == "ultrareview.instructions":       # one paragraph a file, the root's first
                    values.setdefault(key, [])
                    values[key] = values[key] + ([value] if value not in values[key] else [])
                else:
                    values[key] = value
                where[key] = d
        return values, where

    def skip(self) -> list[str]:
        out: list[str] = []
        for d, values in sorted(self.configs.items()):
            for pattern in values.get("review.skip", []):
                try:
                    full = _under(d, pattern)
                except ConfigError as exc:
                    self.problems.append(f"{d + '/' if d else ''}{CONFIG}: {exc}, so it was skipped")
                    continue
                if full not in out:
                    out.append(full)
        return out

    def rules(self) -> list[dict]:
        out: list[dict] = []
        for d in sorted(self.files.found):
            text = self.files.text(d, RULES)
            if text is None:
                continue
            source = f"{d}/{RULES}" if d else RULES
            _, found, problems = parse_rules(text, source)
            self.problems += problems
            for rule in found:
                try:
                    paths = [_under(d, p) for p in rule["paths"]] or ([d + "/"] if d else [])
                except ConfigError as exc:
                    self.problems.append(f"{source}: the rule {rule['heading']!r}: {exc}, so it was skipped")
                    continue
                out.append({"id": rule["id"], "text": rule["text"], "paths": paths})
        return out


def pathspecs(pattern: str) -> list[str]:
    """What ``git diff -- ':(exclude)<p>'`` needs to leave out everything ``pattern`` names.

    A plain pathspec matches a directory by prefix, but one with a wildcard must match the whole
    path, and ``**/`` there always wants a directory: ``svc/**/fixtures/`` (a nested file's
    ``**/fixtures/``) excluded nothing, and ``**/generated/**`` missed a top-level ``generated/``.
    So a wildcard pattern naming a directory also gets ``**`` after it, and every ``**/`` also
    stands for no directory at all."""
    base = pattern
    if any(c in base for c in "*?[") and base.endswith("/"):
        base += "**"
    out: list[str] = []
    todo = [base]
    while todo and len(out) < 16:
        p = todo.pop()
        if p in out:
            continue
        out.append(p)
        start = p.find("**/")
        while start != -1:
            todo.append(p[:start] + p[start + 3:])
            start = p.find("**/", start + 1)
    return out


def merge(per_file: list[dict]) -> dict:
    """One value per setting for the whole change: whatever asks for more review."""
    out: dict = {}
    keys = {k for values in per_file for k in values}
    for key in sorted(keys):
        got = [values.get(key) for values in per_file]
        known = [v for v in got if v is not None]
        s = BY_KEY[key]
        if s.kind == "bool":
            # false only when every changed file's settings say so; true is CloudAEye's default
            if all(v is False for v in got):
                out[key] = False
            elif any(v is True for v in got):
                out[key] = True
        elif key == "ultrareview.instructions":
            lines: list[str] = []
            for value in known:
                lines += [v for v in value if v not in lines]
            out[key] = lines
        elif key in _ORDER:
            out[key] = (min if key in _LOWEST else max)(known, key=_ORDER[key].index)
        elif key in _LOWEST:
            out[key] = min(known)
        elif key in _HIGHEST:
            out[key] = max(known)
        elif known:
            out[key] = known[0]
    return out


def _api_key(values: dict, problems: list[str], key_url: str, key_token: str) -> dict | None:
    """What the skills may know of the file's API key: where it comes from, whether it was found and
    sent. Sent only to CloudAEye's key route for this session (``key_url``), never printed."""
    raw = values.pop("review.api_key")
    where = key_source(raw)
    if values.get("review.llm") != "your own":
        problems.append(f"{CONFIG}: API key is for your own LLM; with LLM: {values.get('review.llm') or 'not set'} "
                        "it is not used")
        return None
    provider = values.get("review.provider")
    if provider not in KEY_PROVIDERS:
        problems.append(f"{CONFIG}: an API key in the file works with Provider {', '.join(KEY_PROVIDERS)}; "
                        f"{provider or 'no provider'} takes its credentials in the CloudAEye console settings, so the key "
                        "here is not used")
        return None
    key = resolve_key(raw)
    status = {"from": where, "found": bool(key) and bool(_KEY_SHAPE.match(key))}
    if not key:
        problems.append(f"{CONFIG}: API key: {where} is not set here, so the key saved in the console settings is used")
    elif not status["found"]:
        problems.append(f"{CONFIG}: API key: {where} does not hold a key, so the key saved in the console settings is used")
    elif key_url:
        status["sent"], why = send_key(key_url, key_token, key)
        if why:
            status["send_error"] = why
            problems.append(f"the API key could not be sent to CloudAEye ({why}), so the key saved in the console settings is used")
    return status


def effective(root: Path, ref: str, changed: list[str], key_url: str = "", key_token: str = "") -> dict:
    fetched = fetch(root, ref) if ref else False
    if ref and _git(root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}").returncode != 0:
        return {"source": ref, "rules": [], "files": [], "problems": [
            f"the settings on {ref.removeprefix('origin/')} could not be read, so CloudAEye's defaults apply"]}
    settings = Settings(Files(root, ref))
    changed = sorted({p.strip().replace("\\", "/") for p in changed if p.strip()})
    per_file = [settings.chain(_dir_of(p))[0] for p in changed] or [settings.chain("")[0]]
    values = merge(per_file)
    values.update({k: v for k, v in settings.configs.get("", {}).items() if root_only(k)})
    if values.get("review.llm") == "CloudAEye" and "review.provider" in values:
        del values["review.provider"]
        settings.problems.append(f"{CONFIG}: Provider is for your own LLM only; with LLM: CloudAEye it was left out")
    if "review.api_key" in values:
        status = _api_key(values, settings.problems, key_url, key_token)
        if status:
            values["review.api_key"] = status
    skip = settings.skip()
    if skip:
        values["review.skip"] = skip
    applied = sorted({d for p in changed for d in _ancestors(_dir_of(p)) if d in settings.configs}
                     or ({""} if "" in settings.configs else set()))
    out = nest(values)
    out.update({
        "rules": settings.rules(),
        "source": ref or "working tree",
        "files": settings.files.paths(),
        "applied": [f"{d}/{CONFIG}" if d else CONFIG for d in applied],
        "problems": settings.problems,
    })
    if ref:
        out["fetched"] = fetched
        pending = [p for p in changed if p.rsplit("/", 1)[-1] in (CONFIG, RULES)]
        if pending:
            out["pending"] = pending
    return out


_OPTIONS = {"bool": ["true", "false"], "score": ["0-100"],
            "paragraph": ["plain words, as long as you like; they can ask for more review, never less"],
            "list": ["paths or patterns, one a line"], "text": ["text, or a file in backticks"],
            "name": ["a model the console offers, or your provider's exact model name"],
            "secret": ["an environment variable that holds the key, like $OPENAI_API_KEY", "the key itself",
                       f"your own LLM with Provider {', '.join(KEY_PROVIDERS)} only"]}
#: what a setting is when no file names it, as show prints it. The hard limits are CloudAEye's own
#: check, and how that check is built is never printed.
DEFAULTS = {"ultrareview.checks": "true", "ultrareview.assign_reviewers": "true", "ultrareview.max_reviewers": "1",
            "ultrareview.instructions": "none", "review.severity_floor": "all",
            "review.llm": "the console setting", "review.provider": "the console setting",
            "review.model": "the console setting", "review.invert_model": "the console setting",
            "review.api_key": "the key saved in the console settings",
            "review.skip": "none", "control_flow.effort": "medium", "control_flow.cross_repo": "true",
            "triage.okrs": "none"}


def show(root: Path, directory: str) -> dict:
    settings = Settings(Files(root))
    mine = settings.configs.get(directory, {})
    inherited, where = settings.chain(directory, upto=False)
    rows = []
    for s in SETTINGS:
        if root_only(s.key) and directory:
            continue                                     # the LLM and triage read the root file only
        from_ = inherited.get(s.key)
        rows.append({
            "key": s.key, "section": s.section, "group": s.group, "label": s.label or s.group,
            "kind": s.kind, "options": list(s.options) or _OPTIONS.get(s.kind, []) or (
                [f"{s.lo}-{s.hi}"] if s.kind == "number" else []),
            "default": next((d for k, d in DEFAULTS.items() if s.key == k or s.key.startswith(k + ".")),
                            "CloudAEye's own check"),
            "value": key_source(mine[s.key]) if s.kind == "secret" and s.key in mine else mine.get(s.key),
            "inherited": from_,
            "inherited_from": ((where[s.key] + "/") if where.get(s.key) else "the root") if from_ is not None
            else None,
        })
    file = f"{directory}/{CONFIG}" if directory else CONFIG
    return {"dir": directory + "/" if directory else "", "file": file,
            "exists": directory in settings.configs or (root / file).is_file(),
            "elsewhere": [p for p in settings.files.paths() if p != file and p.endswith(CONFIG)],
            "settings": rows, "problems": settings.problems}


# ── writing .cloudaeye.config ────────────────────────────────────────────────

def ensure(root: Path, defaults: Path, directory: str, name: str) -> Path:
    """The directory's file, created from the plugin's template when it does not exist yet."""
    path = root / directory / name if directory else root / name
    if not path.exists():
        shutil.copyfile(defaults / TEMPLATES[name], path)
        if directory:
            text = path.read_text(encoding="utf-8-sig")
            if name == CONFIG:
                # the LLM and triage read the root file only; a directory's file offering them would be
                # dead settings
                text = re.sub(r"\n+## Triage PRs\n.*\Z", "\n", text, flags=re.S)
                text = re.sub(r"\n### LLM\n.*?(?=\n### |\n## |\Z)", "", text, flags=re.S)
            lines = text.split("\n")
            if lines and lines[0].startswith("# "):
                lines[0] = f"{lines[0]}: {directory}/"
            path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _block(lines: list[str], s: Setting) -> tuple[int, int] | None:
    """The lines of ``s``'s group (or section, when it has no group): (first, end)."""
    heads = _headings(blank_comments("\n".join(lines)).split("\n"))
    start = None
    section = ""
    for idx, (i, level, title) in enumerate(heads):
        if level == "##":
            section = title
            if section.lower() == s.section.lower() and not s.group:
                start = i
        elif section.lower() == s.section.lower() and title.lower() == s.group.lower():
            start = i
        if start is not None:
            end = next((j for j, lv, _ in heads[idx + 1:] if lv == "##" or s.group), len(lines))
            return start, end
    return None


def _line_re(s: Setting) -> re.Pattern:
    return re.compile(r"^(\s*)(<!--\s*)?-\s*" + re.escape(s.label) + r"\s*:\s*(.*?)\s*(-->)?\s*$", re.I)


def _render(s: Setting, value) -> str:
    if s.kind == "bool":
        return "true" if value else "false"
    if s.kind == "score":
        return f"{value}/100"
    return str(value)


def _setting_line(s: Setting, line: str) -> tuple[bool, str] | None:
    """``(commented, the comment after it)`` when ``line`` holds ``s``, else None.

    The comment after a setting — its options — stays where it is whatever the value becomes,
    and ``column`` keeps it lined up with the others."""
    label = re.escape(s.label)
    m = re.match(r"^\s*<!--\s*-\s*" + label + r"\s*:\s*.*?\s*-->(.*)$", line, re.I) \
        or re.match(r"^\s*-\s*" + label + r"\s*:\s*[^<]*?\s*(<!--.*)?$", line, re.I)
    if not m:
        return None
    return line.lstrip().startswith("<!--"), (m.group(1) or "")


def _with_comment(body: str, line: str, after: str) -> str:
    """``body``, then the comment that followed the setting on ``line``, at the same column."""
    if not after.strip():
        return body
    column = len(line) - len(after.lstrip())
    return body + " " * max(column - len(body), 1) + after.strip()


def _paragraph(s: Setting, value: str) -> list[str]:
    import textwrap

    return textwrap.wrap(f"- {s.label}: {value}", width=96, subsequent_indent="  ",
                         break_long_words=False, break_on_hyphens=False)


def _find_line(lines: list[str], s: Setting, first: int, end: int) -> int | None:
    """The line holding ``s`` in its block, written or commented out — not one inside a longer comment."""
    inside = _comment_lines(lines)
    return next((i for i in range(first + 1, end) if not inside[i] and _setting_line(s, lines[i])), None)


def set_value(text: str, s: Setting, raw: str | None) -> str:
    """``text`` with ``s`` set to ``raw`` (checked), or commented out again when ``raw`` is None."""
    if s.kind == "list":
        raise ConfigError(f"{s.key} holds lines: use add and clear")
    lines = text.split("\n")
    block = _block(lines, s)
    if block is None:
        raise ConfigError(f"the file has no {s.section}{' / ' + s.group if s.group else ''} section")
    first, end = block
    if s.kind == "paragraph":
        return _set_paragraph(lines, s, first, end, raw)
    hit = _find_line(lines, s, first, end)
    if raw is None:
        if hit is not None:
            commented, after = _setting_line(s, lines[hit])
            if not commented:
                body = blank_comments(lines[hit]).strip()       # the options stay outside, never nested
                lines[hit] = _with_comment(f"<!-- {body} -->", lines[hit], after)
        return "\n".join(lines)
    body = f"- {s.label}: {_render(s, value_of(s, raw))}"
    if hit is not None:
        lines[hit] = _with_comment(body, lines[hit], _setting_line(s, lines[hit])[1])
    else:
        lines.insert(_last(lines, first, end) + 1, body)
    return "\n".join(lines)


def _written_paragraph(lines: list[str], s: Setting, first: int, end: int) -> tuple[int, int] | None:
    """Where ``s``'s paragraph is written, outside comments: (its first line, the line past it)."""
    blank = blank_comments("\n".join(lines)).split("\n")
    for i in range(first + 1, end):
        if re.match(r"^\s*-\s*" + re.escape(s.label) + r"\s*:", blank[i], re.I):
            return i, _continuation(blank, i)
    return None


def _set_paragraph(lines: list[str], s: Setting, first: int, end: int, raw: str | None) -> str:
    """The paragraph replaced by ``raw``, wrapped under its label; ``None`` takes it out."""
    new = [] if raw is None else _paragraph(s, value_of(s, raw))
    at = _written_paragraph(lines, s, first, end)
    if at is not None:
        lines[at[0]:at[1]] = new
    elif new:
        after = _last(lines, first, end) + 1
        lines[after:after] = new
    return "\n".join(lines)


def _comment_lines(lines: list[str]) -> list[bool]:
    """Whether each line sits inside a comment that opened on an earlier line."""
    out, open_ = [], False
    for line in lines:
        out.append(open_)
        for m in re.finditer(r"<!--|-->", line):
            open_ = m.group(0) == "<!--"
    return out


def _last(lines: list[str], first: int, end: int) -> int:
    i = end - 1
    while i > first and not lines[i].strip():
        i -= 1
    return i


def add_line(text: str, s: Setting, value: str) -> str:
    """A line added to a list (paths never reviewed), or a sentence added to the end of a paragraph."""
    if s.kind not in ("list", "paragraph"):
        raise ConfigError(f"{s.key} is one value: use set")
    value = " ".join(value.split())
    if not value:
        raise ConfigError("nothing to add")
    if s.kind == "paragraph":
        current, _ = parse_config(text)
        before = current.get(s.key)
        return set_value(text, s, f"{before} {value}" if before else value)
    lines = text.split("\n")
    block = _block(lines, s)
    if block is None:
        raise ConfigError(f"the file has no {s.section} / {s.group} section")
    first, end = block
    value = value.strip("`")
    _under("", value)                                     # a path inside the repository, or refused
    lines.insert(_last(lines, first, end) + 1, f"- {s.label}: `{value}`")
    return "\n".join(lines)


def clear_lines(text: str, s: Setting) -> str:
    if s.kind == "paragraph":
        return set_value(text, s, None) if _block(text.split("\n"), s) else text
    if s.kind != "list":
        raise ConfigError(f"{s.key} is one value: use set with -")
    lines = text.split("\n")
    block = _block(lines, s)
    if block is None:
        return text
    first, end = block
    inside = _comment_lines(lines)
    item = _line_re(s)
    keep = [ln for i, ln in enumerate(lines)
            if not (first < i < end and not inside[i] and not ln.lstrip().startswith("<!--") and item.match(ln))]
    return "\n".join(keep)


# ── .cloudaeye.rules ─────────────────────────────────────────────────────────

def parse_rules(text: str, source: str = RULES) -> tuple[str, list[dict], list[str]]:
    """``(header, rules, problems)``: each rule ``{id, heading, text, paths, raw}``."""
    text = text.lstrip("﻿")
    raw_lines = text.split("\n")
    lines = blank_comments(text).split("\n")
    starts = [i for i, ln in enumerate(lines) if re.match(r"^##\s+\S", ln)]
    header = "\n".join(raw_lines[:starts[0]] if starts else raw_lines).rstrip("\n")
    rules, problems = [], []
    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        heading = lines[start][2:].strip()
        body, paths = [], []
        for ln in lines[start + 1:end]:
            m = re.match(r"^\s*-\s*applies to\s*:\s*(.*)$", ln, re.I)
            if m:
                items = _TICKS.findall(m.group(1)) or [p.strip() for p in m.group(1).split(",")]
                paths.extend(i for i in items if i)
            elif ln.strip():
                body.append(ln.strip())
        rule = {"id": heading if _RULE_ID.match(heading) else "", "heading": heading, "text": " ".join(body),
                "paths": paths, "raw": "\n".join(raw_lines[start:end]).rstrip("\n")}
        if not rule["text"]:
            problems.append(f"{source} line {start + 1}: the rule {heading!r} has no text, so it was skipped")
            continue
        rules.append(rule)
    return header, rules, problems


def _render_rule(rule: dict) -> str:
    out = [f"## {rule['id']}", rule["text"]]
    if rule.get("paths"):
        out.append("- Applies to: " + ", ".join(f"`{p}`" for p in rule["paths"]))
    return "\n".join(out)


def sync_rules(text: str, synced: list[dict]) -> tuple[str, dict]:
    """``text`` with every synced rule replaced by ``synced``; your own rules kept as you wrote them."""
    header, rules, _ = parse_rules(text)
    mine = [r for r in rules if not r["id"]]
    before = {r["id"] for r in rules if r["id"]}
    fresh = []
    for item in synced or []:
        rid = str(item.get("id") or "").strip()
        body = " ".join(str(item.get("text") or "").split())
        if not _RULE_ID.match(rid) or not body:
            continue
        fresh.append({"id": rid, "text": body, "paths": [str(p) for p in item.get("paths") or []]})
    parts = [header.rstrip("\n")] + [_render_rule(r) for r in fresh] + [r["raw"] for r in mine]
    now = {r["id"] for r in fresh}
    return "\n\n".join(p for p in parts if p.strip()) + "\n", {
        "synced": len(fresh), "added": sorted(now - before), "removed": sorted(before - now), "yours": len(mine)}


def seed(root: Path, defaults: Path, answer: str) -> dict:
    """The console's ultrareview settings written into the root ``.cloudaeye.config``.

    ``answer`` is the ``ultrareview_settings`` tool's JSON: only what the console sets apart from the
    defaults, as this file's keys. Nothing to write creates no file; a key this script does not know,
    or a value that is not one of its options, is left out and named."""
    try:
        got = json.loads(answer)
    except ValueError:
        raise ConfigError("the settings answer is not the ultrareview_settings tool's JSON; nothing was written") \
            from None
    if not isinstance(got, dict) or got.get("status") not in (None, "ok"):
        raise ConfigError(f"the console settings could not be read: {(got or {}).get('error') or got}")
    settings = got.get("settings") if isinstance(got.get("settings"), dict) else {}
    if got.get("source") == "none" or not settings:
        return {"file": CONFIG, "source": got.get("source") or "none", "written": False, "set": [],
                "problems": [got["error"]] if got.get("error") else []}
    path = root / CONFIG
    text = (path if path.exists() else defaults / TEMPLATES[CONFIG]).read_text(encoding="utf-8-sig")
    written, problems = [], []
    for key, value in settings.items():
        s = BY_KEY.get(key)
        if s is None or not key.startswith("ultrareview."):
            problems.append(f"{key!r} is not an ultrareview setting this file holds, so it was left out")
            continue
        raw = ("true" if value else "false") if isinstance(value, bool) else str(value)
        try:
            text = set_value(text, s, raw)
        except ConfigError as exc:
            problems.append(f"{exc}; it was left out")
            continue
        written.append(key)
    if not written:                                     # nothing usable: no file appears in the repository
        return {"file": CONFIG, "source": got.get("source"), "written": False, "set": [], "problems": problems}
    path.write_text(text, encoding="utf-8")
    values, found = parse_config(text)
    return {"file": CONFIG, "source": got.get("source"), "written": True, "set": written,
            "values": nest(masked(values)), "problems": problems + found}


# ── the commands ─────────────────────────────────────────────────────────────

def _changed(source: str) -> list[str]:
    if not source:
        return []
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8-sig")
    return [line for line in text.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("effective", "skip", "show", "set", "add", "clear", "rules",
                                            "sync-rules", "seed", "add-rule"))
    parser.add_argument("args", nargs="*")
    parser.add_argument("--root", default="", help="the repository; by default the one holding this directory")
    parser.add_argument("--defaults", default=str(Path(__file__).resolve().parent.parent / "resources" / "config"))
    parser.add_argument("--dir", default="", help="the directory whose files to read or write; the root by default")
    parser.add_argument("--ref", default="", help="effective: read the files at this ref (origin/<target branch>)")
    parser.add_argument("--files", default="", help="effective: the changed paths, one per line, or - for stdin")
    parser.add_argument("--send-key", default="",
                        help="effective: start_session's key_url; the file's API key is sent there, with the "
                             "key_token from CE_KEY_TOKEN, and never printed")
    parser.add_argument("--file", default="",
                        help="sync-rules / seed: the tool's answer (review_rules / ultrareview_settings), or - for stdin")
    parser.add_argument("--heading", default="", help="add-rule: the rule's title")
    parser.add_argument("--text", default="", help="add-rule: the rule in plain words")
    parser.add_argument("--paths", default="", help="add-rule: paths it applies to, comma-separated")
    a = parser.parse_args(argv)
    try:
        root, defaults = repo_root(a.root), Path(a.defaults)
        if a.command == "skip":
            lines = [spec for pattern in Settings(Files(root)).skip() for spec in pathspecs(pattern)]
            # bytes, so Windows writes no carriage return for the shell to keep in a pathspec
            sys.stdout.buffer.write("".join(f"{line}\n" for line in lines).encode("utf-8"))
            return 0
        if a.command == "effective":
            if a.ref and (a.ref.startswith("-") or not _BRANCH.match(a.ref)):
                raise ConfigError(f"{a.ref!r} is not a ref")
            # the session's key token rides in the environment (CE_KEY_TOKEN), never in a printed argument
            result = effective(root, a.ref, _changed(a.files) + a.args, a.send_key,
                               os.environ.get("CE_KEY_TOKEN", "").strip())
        elif a.command == "show":
            result = show(root, norm_dir(root, a.dir))
        elif a.command == "rules":
            directory = norm_dir(root, a.dir)
            path = root / directory / RULES if directory else root / RULES
            text = path.read_text(encoding="utf-8-sig") if path.is_file() else None
            _, rules, problems = parse_rules(text or "")
            result = {"file": path.relative_to(root).as_posix(), "exists": text is not None,
                      "rules": [{k: r[k] for k in ("id", "heading", "text", "paths")} for r in rules],
                      "problems": problems}
        elif a.command == "add-rule":
            directory = norm_dir(root, a.dir)
            heading = " ".join(a.heading.split())
            body = " ".join(a.text.split())
            if not heading or not body or _RULE_ID.match(heading) or heading.startswith("#"):
                raise ConfigError("a rule of your own needs a short title (not an id like r12) and its text")
            paths = [p.strip().strip("`") for p in a.paths.split(",") if p.strip()]
            for p in paths:
                _under(directory, p)
            path = ensure(root, defaults, directory, RULES)
            rule = {"id": heading, "text": body, "paths": paths}
            path.write_text(path.read_text(encoding="utf-8-sig").rstrip("\n") + "\n\n" + _render_rule(rule) + "\n",
                            encoding="utf-8")
            _, rules, problems = parse_rules(path.read_text(encoding="utf-8-sig"))
            result = {"file": path.relative_to(root).as_posix(), "rules": len(rules), "problems": problems}
        elif a.command == "sync-rules":
            source = sys.stdin.read() if a.file == "-" else Path(a.file).read_text(encoding="utf-8-sig")
            try:
                got = json.loads(source)
            except ValueError:
                raise ConfigError("the rules answer is not the review_rules tool's JSON; nothing was synced") from None
            if got.get("status") not in (None, "ok"):
                raise ConfigError(f"the rules could not be read: {got.get('error') or got.get('status')}")
            if not got.get("rules") and not (root / RULES).exists():
                # nothing to sync and nothing synced before: no file appears in the repository
                result = {"file": RULES, "synced": 0, "added": [], "removed": [], "yours": 0, "written": False}
            else:
                path = ensure(root, defaults, "", RULES)
                text, counts = sync_rules(path.read_text(encoding="utf-8-sig"), got.get("rules"))
                path.write_text(text, encoding="utf-8")
                result = {"file": RULES, **counts, "written": True}
        elif a.command == "seed":
            result = seed(root, defaults, sys.stdin.read() if a.file == "-" else
                          Path(a.file).read_text(encoding="utf-8-sig"))
        else:
            directory = norm_dir(root, a.dir)
            path = ensure(root, defaults, directory, CONFIG)
            text = path.read_text(encoding="utf-8-sig")
            if a.command == "set":
                for pair in a.args:
                    key, sep, raw = pair.partition("=")
                    if not sep or key not in BY_KEY:
                        raise ConfigError(f"{pair!r} is not KEY=VALUE with a known key")
                    if root_only(key) and directory:
                        raise ConfigError(f"{BY_KEY[key].label} is read from the repository's top-level "
                                          f"{CONFIG} only")
                    text = set_value(text, BY_KEY[key], None if raw.strip() == "-" else raw)
            elif a.command == "add":
                if len(a.args) != 2 or a.args[0] not in BY_KEY:
                    raise ConfigError("add takes KEY TEXT")
                text = add_line(text, BY_KEY[a.args[0]], a.args[1])
            else:
                if len(a.args) != 1 or a.args[0] not in BY_KEY:
                    raise ConfigError("clear takes KEY")
                text = clear_lines(text, BY_KEY[a.args[0]])
            path.write_text(text, encoding="utf-8")
            values, problems = parse_config(text)
            result = {"file": path.relative_to(root).as_posix(), "values": nest(masked(values)),
                      "problems": problems}
    except (ConfigError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
