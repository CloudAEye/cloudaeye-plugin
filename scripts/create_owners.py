#!/usr/bin/env python3
"""/cloudaeye:create-owners: write OWNERS.md files from the repository's git history.

Local only: git and Python, no network, no CloudAEye call, no model. Prints one
JSON object describing what it did (or, with --dry-run, would do).

    create_owners.py [PATH] [--depth N] [--dry-run] [--alias "Git Name=login" ...]
                     [--team NAME --team-lead LOGIN [--member LOGIN ...]]
    create_owners.py --collect

``--collect`` blames nothing and writes nothing: it prints every OWNERS.md in the
working tree as ``{"owners": {path: text}}``, which /cloudaeye:assign-reviewer
sends while the target branch has none of its own.

The format and every rule are CloudAEye's OWNERS.md spec:

- **Contributors** is measured: each person's share of the lines standing in a
  folder that were written in the last 12 months (all lines when fewer than 200
  were), by ``git blame -w -M -C`` through ``.mailmap``. The largest share is the
  lead contributor. This section is the script's: it is rewritten on a later run,
  and only when a share moved 5 points or someone joined or left the list.
- **Teams** is people's: one line per team, ``- Cloud: @lead (lead), @member``.
  It starts blank and the script never removes or rewrites a line of it; it only
  adds the team the person running it names with ``--team``.

Where files go: PATH (default the repository root) is level 0 and always gets a
file. Every folder down to ``--depth`` levels below it (default 3) gets its own
only when the people who wrote it differ from the rest of the area it sits in:
similarity = the sum, person by person, of the smaller of their share of the
folder and their share of the rest of the area; below 0.70 it gets a file. A
folder holding 90% or more of its parent's code is passed through and uses up no
level; a folder under 500 lines is too small for a file of its own. A folder
that already has an OWNERS.md keeps it.

Only GitHub handles are written. An author becomes a handle from a GitHub
noreply address, from a name whose letters spell a login seen in the history,
or from ``--alias``; anyone else is listed in a comment as needing a handle. No
email address is ever written. Bots are left out of every count.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

OWNERS = "OWNERS.md"
WINDOW_DAYS = 365
MIN_RECENT = 200
MIN_AREA = 500
CUTOFF = 0.70
PASS_THROUGH = 0.90
ROOT_MIN, ROOT_MAX = 0.01, 30
AREA_MIN, AREA_MAX = 0.05, 10
REFRESH_POINTS = 0.05
DEFAULT_DEPTH = 3

LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
NOREPLY = re.compile(r"^(?:\d+\+)?([^@\s]+)@users\.noreply\.github\.com$", re.I)
BOT = re.compile(r"\[bot\]|dependabot|renovate|github-actions|snyk-bot|greenkeeper", re.I)
SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "go.sum", "Cargo.lock",
              "composer.lock", "Gemfile.lock", OWNERS}
SKIP_DIRS = {"vendor", "node_modules", "third_party", "dist", "build", ".git"}
DATA_SUFFIXES = {".json", ".jsonl", ".csv", ".tsv", ".svg", ".snap", ".ipynb", ".xml", ".lock"}
GENERATED = re.compile(r"(\.min\.(js|css)$|\.pb\.go$|_pb2\.py$|\.generated\.)", re.I)


class Fail(RuntimeError):
    pass


def git(*args: str, cwd: str | None = None, check: bool = True) -> str:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    try:
        out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", env=env, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Fail(f"git {args[0]} failed: {exc}") from exc
    if check and out.returncode != 0:
        raise Fail(f"git {args[0]} failed: {out.stderr.strip()[:200]}")
    return out.stdout


# ── who wrote what ────────────────────────────────────────────────────────────

def text_files(root: str, start: str) -> list[str]:
    scope = [start] if start else []
    tracked = git("ls-files", "-z", "--", *scope, cwd=root).split("\0")
    textual = set(git("grep", "-I", "-l", "-e", "", "--", *(scope or ["."]), cwd=root, check=False).splitlines())
    out = []
    for f in tracked:
        if not f or f not in textual:
            continue
        p = PurePosixPath(f)
        if (p.name in SKIP_NAMES or p.suffix.lower() in DATA_SUFFIXES or GENERATED.search(p.name)
                or SKIP_DIRS & set(p.parts[:-1])):
            continue
        out.append(f)
    return out


def blame(root: str, path: str) -> list[tuple[str, str, int]]:
    out = git("blame", "--line-porcelain", "-w", "-M", "-C", "HEAD", "--", path, cwd=root, check=False)
    rows, name, email, when = [], "", "", 0
    for line in out.splitlines():
        if line.startswith("author "):
            name = line[7:]
        elif line.startswith("author-mail "):
            email = line[12:].strip("<>")
        elif line.startswith("author-time "):
            when = int(line[12:] or 0)
        elif line.startswith("\t"):
            rows.append((name, email, when))
    return rows


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def identities(pairs: set[tuple[str, str]], aliases: dict[str, str]) -> tuple[dict[tuple[str, str], str], dict]:
    """(name, email) -> a GitHub login, or the git name when none can be shown. Never an email."""
    logins = {}
    for name, email in pairs:
        m = NOREPLY.match(email or "")
        if m:
            logins[_norm(m.group(1))] = m.group(1)
            logins.setdefault(_norm(name), m.group(1))
    by_email: dict[str, str] = {}
    for name, email in pairs:
        m = NOREPLY.match(email or "")
        if m:
            by_email[(email or "").lower()] = m.group(1)
    for name, email in pairs:                           # a name written with an address that has a login
        login = logins.get(_norm(name))
        if login and email and not NOREPLY.match(email):
            by_email.setdefault(email.lower(), login)
    alias = {_norm(k): v for k, v in aliases.items()}
    out: dict[tuple[str, str], str] = {}
    for name, email in pairs:
        m = NOREPLY.match(email or "")
        who = (m.group(1) if m else alias.get(_norm(name)) or by_email.get((email or "").lower())
               or logins.get(_norm(name)) or name.strip() or "unknown")
        out[(name, email)] = who
    return out, {}


def is_bot(name: str, email: str) -> bool:
    return bool(BOT.search(name or "") or BOT.search(email or ""))


def folders_of(path: str, start: str) -> list[str]:
    parts = PurePosixPath(path).parts[:-1]
    out = [""] + ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]
    return [f for f in out if not start or f == start or f.startswith(start + "/")]


# ── where files go ────────────────────────────────────────────────────────────

def shares(c: Counter) -> dict[str, float]:
    total = sum(c.values())
    return {k: v / total for k, v in c.items()} if total else {}


def similarity(a: Counter, b: Counter) -> float:
    sa, sb = shares(a), shares(b)
    return sum(min(sa.get(k, 0.0), sb.get(k, 0.0)) for k in set(sa) | set(sb))


def place(start: str, depth: int, counts, children: dict[str, list[str]], existing: set[str]) -> tuple[set, list]:
    """The folders that get an OWNERS.md, and the decisions behind each one judged."""
    files, decisions = {start}, []

    def lines(d: str) -> int:
        return sum(counts(d).values())

    def decide(folder: str, anchor: str, level: int) -> None:
        for c in sorted(children.get(folder, [])):
            lc = lines(c)
            if c in existing:
                files.add(c)
                decisions.append({"folder": c, "result": "already has one"})
                if level + 1 < depth:
                    decide(c, c, level + 1)
                continue
            if lc >= PASS_THROUGH * max(1, lines(folder)):
                decide(c, anchor, level)
                continue
            if lc < MIN_AREA:
                continue
            rest = counts(anchor) - counts(c)
            sim = similarity(counts(c), rest) if rest else 1.0
            own = sim < CUTOFF
            decisions.append({"folder": c, "level": level + 1, "lines": lc, "similarity": round(sim, 2),
                              "result": "own file" if own else "uses the file above"})
            if own:
                files.add(c)
            if level + 1 < depth:
                decide(c, c if own else anchor, level + 1)

    decide(start, start, 0)
    return files, decisions


# ── the file ──────────────────────────────────────────────────────────────────

_HEADING = re.compile(r"^\s*##\s*(contributors|teams)\b", re.I | re.M)
_SECTION = re.compile(r"(^\s*##\s*contributors\b.*?)(?=^\s*##\s|\Z)", re.I | re.M | re.S)
_LISTED = re.compile(r"^\s*[-*+]\s+(?:lead contributor:\s*)?@([A-Za-z0-9-]+)\s*\(?\s*(<\s*1|\d+(?:\.\d+)?)?\s*%?",
                     re.I | re.M)


def contributors_block(c: Counter, *, root: bool, head: str, today: str, windowed: bool) -> tuple[str, list, list]:
    total = sum(c.values())
    lo, cap = (ROOT_MIN, ROOT_MAX) if root else (AREA_MIN, AREA_MAX)
    ranked = sorted(c.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    handles = [(k, v / total) for k, v in ranked if LOGIN.fullmatch(k) and v / total >= lo][:cap]
    unresolved = [(k, v / total) for k, v in ranked if not LOGIN.fullmatch(k) and v / total >= lo]
    rest = len([1 for k, v in ranked if LOGIN.fullmatch(k)]) - len(handles)
    window = ("lines from the last 12 months" if windowed
              else f"all lines (fewer than {MIN_RECENT} in the last 12 months)")
    out = ["## Contributors",
           f"<!-- Filled in by /cloudaeye:create-owners from git blame at {head} on {today},",
           f"     {window}. It rewrites this section when run again. -->"]
    for i, (k, s) in enumerate(handles):
        pct = f"{s:.0%}" if s >= 0.01 else "<1%"
        out.append(f"- Lead contributor: @{k} ({pct})" if i == 0 else f"- @{k} {pct}")
    if rest > 0:
        out.append(f"<!-- and {rest} more under {lo:.0%} -->")
    for k, s in unresolved:
        out.append(f"<!-- needs a GitHub handle: {k} {s:.0%} -->")
    return "\n".join(out) + "\n", handles, unresolved


TEAMS_BLANK = ("## Teams\n<!-- Optional. Anyone can fill this in, any time. One line per team, its lead marked:\n"
               "     - Payments: @alice (lead), @bob -->\n")


def current_shares(text: str) -> dict[str, float]:
    m = _SECTION.search(text)
    if not m:
        return {}
    out = {}
    for login, pct in _LISTED.findall(re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S)):
        out[login.lower()] = 0.005 if pct and pct.replace(" ", "") == "<1" else (float(pct) / 100 if pct else 0.0)
    return out


def moved(old: dict[str, float], new: list[tuple[str, float]]) -> bool:
    fresh = {k.lower(): s for k, s in new}
    if set(old) != set(fresh):
        return True
    return any(abs(old[k] - fresh[k]) >= REFRESH_POINTS for k in fresh)


def add_team(text: str, team: str, lead: str, members: list[str]) -> tuple[str, str]:
    """``text`` with the team line added or extended; never a line removed. Returns (text, what happened)."""
    people = [f"@{lead} (lead)"] if lead else []
    people += [f"@{m}" for m in members if m and m.lower() != (lead or "").lower()]
    if not re.search(r"^\s*##\s*teams\b", text, re.I | re.M):
        text = text.rstrip("\n") + "\n\n" + TEAMS_BLANK
    lines = text.split("\n")
    in_teams, at = False, None
    for i, line in enumerate(lines):
        if re.match(r"^\s*##\s*", line):
            in_teams = bool(re.match(r"^\s*##\s*teams\b", line, re.I))
            continue
        if in_teams and re.match(rf"^\s*[-*+]\s+{re.escape(team)}\s*:", line, re.I):
            at = i
            break
    if at is None:
        end = len(lines)
        idx = next(i for i, l in enumerate(lines) if re.match(r"^\s*##\s*teams\b", l, re.I))
        for j in range(idx + 1, len(lines)):
            if re.match(r"^\s*##\s", lines[j]):
                end = j
                break
        while end > idx + 1 and not lines[end - 1].strip():
            end -= 1
        lines.insert(end, f"- {team}: " + ", ".join(people))
        return "\n".join(lines), "added"
    have = lines[at]
    if lead and "(lead)" in have.lower() and f"@{lead.lower()} (lead)" not in have.lower():
        return text, f"kept: {team} already names another lead"
    missing = [p for p in people if p.split()[0].lower() not in have.lower()]
    if not missing:
        return text, "unchanged"
    lines[at] = have.rstrip() + ", " + ", ".join(missing)
    return "\n".join(lines), "extended"


# ── the run ───────────────────────────────────────────────────────────────────

def existing_owners(root: str, start: str) -> set[str]:
    """Folders (relative, "" the root) under ``start`` that already have an OWNERS.md, tracked or not."""
    out = set()
    base = Path(root) / start if start else Path(root)
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        if OWNERS in filenames:
            rel = Path(dirpath).relative_to(root).as_posix()
            out.add("" if rel == "." else rel)
    return out


def run(args) -> dict:
    root = git("rev-parse", "--show-toplevel").strip()
    if not root:
        raise Fail("not inside a git repository")
    head = git("rev-parse", "--short", "HEAD", cwd=root).strip()
    shallow = git("rev-parse", "--is-shallow-repository", cwd=root).strip() == "true"
    start = ""
    if args.path not in ("", "."):
        absolute = Path(args.path).resolve()
        try:
            start = absolute.relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            raise Fail(f"{args.path} is not inside this repository")
        if not absolute.is_dir():
            raise Fail(f"{args.path} is not a folder")
        start = "" if start == "." else start
    aliases = {}
    for a in args.alias or []:
        name, _, login = a.partition("=")
        if not LOGIN.fullmatch(login.strip().lstrip("@")):
            raise Fail(f"--alias {a!r}: the part after = must be a GitHub username")
        aliases[name.strip()] = login.strip().lstrip("@")

    files = text_files(root, start)
    with ThreadPoolExecutor(max_workers=8) as pool:
        blamed = dict(zip(files, pool.map(lambda f: blame(root, f), files)))
    pairs = {(n, e) for rows in blamed.values() for n, e, _ in rows if not is_bot(n, e)}
    who, _ = identities(pairs, aliases)
    cutoff = time.time() - WINDOW_DAYS * 86400
    recent: dict[str, Counter] = defaultdict(Counter)
    every: dict[str, Counter] = defaultdict(Counter)
    for f, rows in blamed.items():
        for n, e, when in rows:
            if is_bot(n, e):
                continue
            k = who[(n, e)]
            for d in folders_of(f, start):
                every[d][k] += 1
                if when >= cutoff:
                    recent[d][k] += 1

    def counts(d: str) -> Counter:
        r = recent.get(d, Counter())
        return r if sum(r.values()) >= MIN_RECENT else every.get(d, Counter())

    children: dict[str, list[str]] = defaultdict(list)
    for d in every:
        if d and d != start:
            parent = str(PurePosixPath(d).parent)
            children["" if parent == "." else parent].append(d)
    existing = existing_owners(root, start)
    chosen, decisions = place(start, max(0, args.depth), counts, children, existing)

    today = time.strftime("%Y-%m-%d")
    results, unresolved_all = [], Counter()
    for folder in sorted(chosen, key=lambda d: (d.count("/") if d else -1, d)):
        is_root = folder == ""
        # an area's numbers cover the code it governs: its folder, less the sub-folders with a file of their own;
        # the root's cover the whole repository, because the root lists everyone
        nested = [o for o in chosen if o != folder and (is_root or o.startswith(folder + "/"))]
        outermost = [o for o in nested if not any(x != o and o.startswith(x + "/") for x in nested)]
        governed = counts(folder) if is_root else counts(folder) - sum((counts(o) for o in outermost), Counter())
        windowed = sum(recent.get(folder, Counter()).values()) >= MIN_RECENT
        block, handles, unresolved = contributors_block(governed, root=is_root, head=head, today=today,
                                                        windowed=windowed)
        for k, s in unresolved:
            unresolved_all[k] = max(unresolved_all[k], round(s, 3))
        path = Path(root) / (folder or ".") / OWNERS
        rel = (f"{folder}/{OWNERS}" if folder else OWNERS)
        entry = {"path": rel, "lead_contributor": handles[0][0] if handles else None,
                 "contributors": [[k, round(s, 3)] for k, s in handles],
                 "unresolved": [[k, round(s, 3)] for k, s in unresolved]}
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if not _HEADING.search(re.sub(r"<!--.*?-->", "", text, flags=re.S)):
                entry["action"] = "older format: left as it is"
                results.append(entry)
                continue
            if _SECTION.search(text) and not moved(current_shares(text), handles):
                entry["action"] = "unchanged"
                new_text = text
            else:
                new_text = (_SECTION.sub(lambda m: block + "\n", text, count=1) if _SECTION.search(text)
                            else re.sub(r"^(\s*##\s*teams\b)", block + "\n\\1", text, count=1, flags=re.I | re.M))
                entry["action"] = "contributors updated"
        else:
            title = "# Owners" if is_root else f"# Owners: {folder}"
            new_text = f"{title}\n\n{block}\n{TEAMS_BLANK}"
            entry["action"] = "created"
        if args.team and folder == start:
            new_text, team_action = add_team(new_text, args.team.strip(), (args.team_lead or "").lstrip("@"),
                                             [m.lstrip("@") for m in args.member or []])
            entry["team"] = team_action
            if entry["action"] == "unchanged" and team_action in ("added", "extended"):
                entry["action"] = "team added"
        if not args.dry_run and entry["action"] in ("created", "contributors updated", "team added"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new_text, encoding="utf-8", newline="\n")
        entry["written"] = not args.dry_run and entry["action"] in ("created", "contributors updated", "team added")
        results.append(entry)

    name = git("config", "user.name", cwd=root, check=False).strip()
    email = git("config", "user.email", cwd=root, check=False).strip()
    m = NOREPLY.match(email)
    runner = m.group(1) if m else who.get((name, email)) if (name, email) in who else aliases.get(name)
    return {
        "status": "ok", "repository": root, "start": start or ".", "depth": args.depth, "head": head,
        "dry_run": bool(args.dry_run), "shallow": shallow, "files_scanned": len(files),
        "owners_files": results, "decisions": decisions,
        "needs_a_handle": [[k, s] for k, s in unresolved_all.most_common()],
        "runner": {"name": name, "login": runner if runner and LOGIN.fullmatch(runner) else None},
    }


#: The largest OWNERS.md --collect prints, and how many: what CloudAEye reads from a working tree.
MAX_COLLECT_BYTES = 32_000
MAX_COLLECT_FILES = 60


def collect() -> dict:
    """Every OWNERS.md in the working tree, tracked or not, root first: the files, not a measurement."""
    root = git("rev-parse", "--show-toplevel").strip()
    if not root:
        raise Fail("not inside a git repository")
    owners, skipped = {}, []
    for folder in sorted(existing_owners(root, ""), key=lambda d: (d.count("/") if d else -1, d)):
        rel = f"{folder}/{OWNERS}" if folder else OWNERS
        text = (Path(root) / rel).read_text(encoding="utf-8", errors="replace")
        if len(text.encode("utf-8")) > MAX_COLLECT_BYTES:
            skipped.append({"path": rel, "reason": f"larger than {MAX_COLLECT_BYTES:,} bytes"})
        elif len(owners) >= MAX_COLLECT_FILES:
            skipped.append({"path": rel, "reason": f"past the first {MAX_COLLECT_FILES} files"})
        else:
            owners[rel] = text
    return {"status": "ok", "repository": root, "owners": owners, "skipped": skipped}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", default="")
    ap.add_argument("--collect", action="store_true", help="print the working tree's OWNERS.md files and stop")
    ap.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--alias", action="append", help='"Git Name=login": the GitHub handle for a git author')
    ap.add_argument("--team", default="")
    ap.add_argument("--team-lead", default="")
    ap.add_argument("--member", action="append")
    args = ap.parse_args()
    if args.collect:
        try:
            out = collect()
        except Fail as exc:
            print(json.dumps({"status": "error", "error": str(exc)}))
            return 1
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(out, indent=1))
        return 0
    if args.team and not (args.team_lead or args.member):
        print(json.dumps({"status": "error", "error": "--team needs --team-lead or --member"}))
        return 1
    for login in [args.team_lead, *(args.member or [])]:
        if login and not LOGIN.fullmatch(login.lstrip("@")):
            print(json.dumps({"status": "error", "error": f"{login!r} is not a GitHub username"}))
            return 1
    try:
        out = run(args)
    except Fail as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
