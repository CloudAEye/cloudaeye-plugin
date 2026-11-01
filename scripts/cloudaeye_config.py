#!/usr/bin/env python3
"""Read and write CloudAEye's settings files in a repository: .cloudaeye.config and .cloudaeye.rules.

A pair can sit in any directory and covers that directory and everything below it:
  <repo>/.cloudaeye.config, .cloudaeye.rules        the whole repository; most teams need only these
  <repo>/services/payments/.cloudaeye.config, ...   services/payments/ and below; wins over the files
                                                    above it, setting by setting

Both are markdown. A new file starts from the plugin's template (resources/config/), where every
setting is commented out with its options beside it.

Which settings apply to a change: each changed file takes the nearest value of each setting,
walking up to the root; instructions, paths never reviewed and rules add up on the way. Across its
files the change takes whatever asks for more review: the lowest limit, the most reviewers, the
lowest severity floor, a check left on unless every file's settings turn it off. Triage reads the
root file only. Before a commit the files are read from the working tree; on a pull request from
its target branch (--ref), so a pull request cannot change its own settings.

Commands, each printing JSON (skip prints lines):
  effective [--ref REF] [--files F|-] [-- PATH...]   the settings and rules that apply to a change
  skip                                    every directory's paths never reviewed, as git pathspecs, one per line
  show [--dir D]                          D's settings: options, its value, what it inherits
  set [--dir D] KEY=VALUE...              write values; VALUE "-" comments the setting out again
  add [--dir D] KEY TEXT                  add a line to a list setting (instructions, skip)
  clear [--dir D] KEY                     remove every line of a list setting
  rules [--dir D]                         the rules in D's .cloudaeye.rules
  sync-rules --file F|-                   your organisation's rules (review_rules' answer) into the root file
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
    label: str            # the text before ":"; "" for free lines (instructions)
    kind: str             # onoff | yesno | choice | score | number | text | list | lines
    options: tuple = ()
    lo: int = 0
    hi: int = 0


SETTINGS = (
    Setting("ultrareview.checks.checklist", "Ultrareview", "Checks", "PR checklist", "onoff"),
    Setting("ultrareview.checks.review", "Ultrareview", "Checks", "Review (bugs and security)", "onoff"),
    Setting("ultrareview.checks.slop", "Ultrareview", "Checks", "AI slop score", "onoff"),
    Setting("ultrareview.checks.risk", "Ultrareview", "Checks", "Risk score", "onoff"),
    Setting("ultrareview.checks.architecture", "Ultrareview", "Checks", "Architecture", "onoff"),
    Setting("ultrareview.checks.control_flow", "Ultrareview", "Checks", "Control flow", "onoff"),
    Setting("ultrareview.checks.task", "Ultrareview", "Checks", "Task check", "onoff"),
    Setting("ultrareview.limits.risk", "Ultrareview", "Limits", "Risk score", "score"),
    Setting("ultrareview.limits.slop", "Ultrareview", "Limits", "AI slop score", "score"),
    Setting("ultrareview.limits.severity", "Ultrareview", "Limits", "Review severity", "choice", ("medium", "low")),
    Setting("ultrareview.reviewers", "Ultrareview", "Reviewers", "Reviewers", "choice", ("1", "2", "3")),
    Setting("ultrareview.instructions", "Ultrareview", "Instructions", "", "lines"),
    Setting("review.severity_floor", "Review", "Severity floor", "Severity floor", "choice",
            ("all", "critical", "high", "medium", "low")),
    Setting("review.skip", "Review", "Paths never reviewed", "Skip", "list"),
    Setting("control_flow.depth", "Control flow", "", "Depth", "choice", ("1", "2", "3")),
    Setting("control_flow.cross_repo", "Control flow", "", "Across repositories", "yesno"),
    Setting("triage.okrs", "Triage PRs", "", "OKRs", "text"),
    Setting("triage.show", "Triage PRs", "", "Show", "number", lo=1, hi=50),
    Setting("triage.label", "Triage PRs", "", "Label without asking", "yesno"),
)
BY_KEY = {s.key: s for s in SETTINGS}
#: across a change's files, the value that asks for more review
_LOWEST = {"ultrareview.limits.risk", "ultrareview.limits.slop", "ultrareview.limits.severity",
           "review.severity_floor"}
_HIGHEST = {"ultrareview.reviewers", "control_flow.depth"}
_ORDER = {"ultrareview.limits.severity": ("low", "medium"),
          "review.severity_floor": ("all", "low", "medium", "high", "critical")}
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
            return got.stdout.decode("utf-8", "replace") if got.returncode == 0 else None
        try:
            return (self.root / path).read_text(encoding="utf-8")
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


def value_of(s: Setting, raw: str):
    """The value as the other skills use it, or ``ConfigError`` naming the options."""
    text = raw.strip()
    low = text.lower()
    if s.kind in ("onoff", "yesno"):
        if low in ON:
            return True
        if low in OFF:
            return False
        raise ConfigError(f"{s.label}: {text!r} is not {'on or off' if s.kind == 'onoff' else 'yes or no'}")
    if s.kind == "choice":
        if low not in s.options:
            raise ConfigError(f"{s.label}: {text!r} is not one of {' | '.join(s.options)}")
        return int(low) if low.isdigit() else low
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


def parse_config(text: str, source: str = CONFIG) -> tuple[dict, list[str]]:
    """``({key: value}, problems)`` for every setting written outside a comment."""
    values: dict = {}
    problems: list[str] = []
    section = group = ""
    for n, line in enumerate(blank_comments(text).split("\n"), 1):
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
        free = next((s for s in SETTINGS if s.kind == "lines" and s.section.lower() == section.lower()
                     and s.group.lower() == group.lower()), None)
        if free is not None:
            values.setdefault(free.key, []).append(item.group(1))
            continue
        kv = re.match(r"^([^:]+?)\s*:\s*(.*)$", item.group(1))
        setting = _find(section, group, kv.group(1)) if kv else None
        if setting is None:
            problems.append(f"{source} line {n}: {item.group(1)!r} is not a setting here, so it was skipped")
            continue
        try:
            value = value_of(setting, kv.group(2))
        except ConfigError as exc:
            problems.append(f"{source} line {n}: {exc}; the default stands")
            continue
        if setting.kind == "list":
            values.setdefault(setting.key, []).extend(value)
        else:
            values[setting.key] = value
    return values, problems


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
                values, found = parse_config(text, f"{directory}/{CONFIG}" if directory else CONFIG)
                self.configs[directory] = values
                self.problems += found

    def chain(self, directory: str, upto: bool = True) -> tuple[dict, dict]:
        """``(values, where)`` in force in ``directory``: the nearest file wins, instructions add up.

        ``upto=False`` stops above ``directory``: what a file there would inherit."""
        values: dict = {}
        where: dict = {}
        dirs = _ancestors(directory)
        for d in dirs if upto else dirs[:-1]:
            for key, value in self.configs.get(d, {}).items():
                if key == "review.skip" or key.startswith("triage."):
                    continue
                if key == "ultrareview.instructions":
                    values.setdefault(key, [])
                    values[key] = values[key] + [v for v in value if v not in values[key]]
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
        if s.kind in ("onoff", "yesno"):
            # off only when every changed file's settings turn it off; on is CloudAEye's default
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
            out[key] = min(known, key=_ORDER[key].index)
        elif key in _LOWEST:
            out[key] = min(known)
        elif key in _HIGHEST:
            out[key] = max(known)
        elif known:
            out[key] = known[0]
    return out


def effective(root: Path, ref: str, changed: list[str]) -> dict:
    fetched = fetch(root, ref) if ref else False
    if ref and _git(root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}").returncode != 0:
        return {"source": ref, "rules": [], "files": [], "problems": [
            f"the settings on {ref.removeprefix('origin/')} could not be read, so CloudAEye's defaults apply"]}
    settings = Settings(Files(root, ref))
    changed = sorted({p.strip().replace("\\", "/") for p in changed if p.strip()})
    per_file = [settings.chain(_dir_of(p))[0] for p in changed] or [settings.chain("")[0]]
    values = merge(per_file)
    values.update({k: v for k, v in settings.configs.get("", {}).items() if k.startswith("triage.")})
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


def show(root: Path, directory: str) -> dict:
    settings = Settings(Files(root))
    mine = settings.configs.get(directory, {})
    inherited, where = settings.chain(directory, upto=False)
    rows = []
    for s in SETTINGS:
        if s.key.startswith("triage.") and directory:
            continue                                     # triage reads the root file only
        from_ = inherited.get(s.key)
        rows.append({
            "key": s.key, "section": s.section, "group": s.group, "label": s.label or s.group,
            "kind": s.kind, "options": list(s.options) or (
                ["on", "off"] if s.kind == "onoff" else ["yes", "no"] if s.kind == "yesno" else
                ["0-100"] if s.kind == "score" else [f"{s.lo}-{s.hi}"] if s.kind == "number" else []),
            "value": mine.get(s.key),
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
            lines = path.read_text(encoding="utf-8").split("\n")
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
    if s.kind in ("onoff",):
        return "on" if value else "off"
    if s.kind == "yesno":
        return "yes" if value else "no"
    if s.kind == "score":
        return f"{value}/100"
    return str(value)


def set_value(text: str, s: Setting, raw: str | None) -> str:
    """``text`` with ``s`` set to ``raw`` (checked), or commented out again when ``raw`` is None."""
    if s.kind in ("list", "lines"):
        raise ConfigError(f"{s.key} holds lines: use add and clear")
    lines = text.split("\n")
    block = _block(lines, s)
    if block is None:
        raise ConfigError(f"the file has no {s.section}{' / ' + s.group if s.group else ''} section")
    first, end = block
    pattern = _line_re(s)
    inside = _comment_lines(lines)
    hit = next((i for i in range(first + 1, end) if not inside[i] and pattern.match(lines[i])), None)
    if raw is None:
        if hit is not None and not pattern.match(lines[hit]).group(2):
            lines[hit] = f"<!-- {lines[hit].strip()} -->"
        return "\n".join(lines)
    value = value_of(s, raw)
    new = f"- {s.label}: {_render(s, value)}"
    if hit is not None:
        lines[hit] = new
    else:
        lines.insert(_last(lines, first, end) + 1, new)
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
    if s.kind not in ("list", "lines"):
        raise ConfigError(f"{s.key} is one value: use set")
    value = " ".join(value.split())
    if not value:
        raise ConfigError("nothing to add")
    lines = text.split("\n")
    block = _block(lines, s)
    if block is None:
        raise ConfigError(f"the file has no {s.section} / {s.group} section")
    first, end = block
    if s.kind == "list":
        value = value.strip("`")
        _under("", value)                                 # a path inside the repository, or refused
        new = f"- {s.label}: `{value}`"
    else:
        new = f"- {value}"
    lines.insert(_last(lines, first, end) + 1, new)
    return "\n".join(lines)


def clear_lines(text: str, s: Setting) -> str:
    if s.kind not in ("list", "lines"):
        raise ConfigError(f"{s.key} is one value: use set with -")
    lines = text.split("\n")
    block = _block(lines, s)
    if block is None:
        return text
    first, end = block
    inside = _comment_lines(lines)
    item = _line_re(s) if s.kind == "list" else re.compile(r"^\s*-\s+\S")
    keep = [ln for i, ln in enumerate(lines)
            if not (first < i < end and not inside[i] and not ln.lstrip().startswith("<!--") and item.match(ln))]
    return "\n".join(keep)


# ── .cloudaeye.rules ─────────────────────────────────────────────────────────

def parse_rules(text: str, source: str = RULES) -> tuple[str, list[dict], list[str]]:
    """``(header, rules, problems)``: each rule ``{id, heading, text, paths, raw}``."""
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


# ── the commands ─────────────────────────────────────────────────────────────

def _changed(source: str) -> list[str]:
    if not source:
        return []
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("effective", "skip", "show", "set", "add", "clear", "rules",
                                            "sync-rules", "add-rule"))
    parser.add_argument("args", nargs="*")
    parser.add_argument("--root", default="", help="the repository; by default the one holding this directory")
    parser.add_argument("--defaults", default=str(Path(__file__).resolve().parent.parent / "resources" / "config"))
    parser.add_argument("--dir", default="", help="the directory whose files to read or write; the root by default")
    parser.add_argument("--ref", default="", help="effective: read the files at this ref (origin/<target branch>)")
    parser.add_argument("--files", default="", help="effective: the changed paths, one per line, or - for stdin")
    parser.add_argument("--file", default="", help="sync-rules: review_rules' answer, or - to read it from stdin")
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
            result = effective(root, a.ref, _changed(a.files) + a.args)
        elif a.command == "show":
            result = show(root, norm_dir(root, a.dir))
        elif a.command == "rules":
            directory = norm_dir(root, a.dir)
            path = root / directory / RULES if directory else root / RULES
            text = path.read_text(encoding="utf-8") if path.is_file() else None
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
            path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + _render_rule(rule) + "\n",
                            encoding="utf-8")
            _, rules, problems = parse_rules(path.read_text(encoding="utf-8"))
            result = {"file": path.relative_to(root).as_posix(), "rules": len(rules), "problems": problems}
        elif a.command == "sync-rules":
            source = sys.stdin.read() if a.file == "-" else Path(a.file).read_text(encoding="utf-8")
            got = json.loads(source)
            if got.get("status") not in (None, "ok"):
                raise ConfigError(f"the rules could not be read: {got.get('error') or got.get('status')}")
            if not got.get("rules") and not (root / RULES).exists():
                # nothing to sync and nothing synced before: no file appears in the repository
                result = {"file": RULES, "synced": 0, "added": [], "removed": [], "yours": 0, "written": False}
            else:
                path = ensure(root, defaults, "", RULES)
                text, counts = sync_rules(path.read_text(encoding="utf-8"), got.get("rules"))
                path.write_text(text, encoding="utf-8")
                result = {"file": RULES, **counts, "written": True}
        else:
            directory = norm_dir(root, a.dir)
            path = ensure(root, defaults, directory, CONFIG)
            text = path.read_text(encoding="utf-8")
            if a.command == "set":
                for pair in a.args:
                    key, sep, raw = pair.partition("=")
                    if not sep or key not in BY_KEY:
                        raise ConfigError(f"{pair!r} is not KEY=VALUE with a known key")
                    if key.startswith("triage.") and directory:
                        raise ConfigError("triage settings are read from the root file only")
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
            result = {"file": path.relative_to(root).as_posix(), "values": nest(values), "problems": problems}
    except (ConfigError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
