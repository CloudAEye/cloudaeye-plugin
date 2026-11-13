#!/usr/bin/env python3
"""Prepare and upload the change a CloudAEye command reviews. One script, so no skill carries the shell.

    python cloudaeye_session.py head
        Print {"branch": ..., "head": ...} for start_session, and make `.cloudaeye/` (git-ignored).

    python cloudaeye_session.py start [--scope <path>] [--settings] [--review] [--pr] [--author]
                                      [--guide <name>]
        Print, as one JSON line, everything `start_session` is called with: the repository
        (`repo`, `provider`, `repo_url`), `branch` and `head`. When an earlier upload from this
        checkout left its target branch behind, the change is worked out now, exactly as
        `upload` would, and the line also carries `diff_sha256`, `diff_base` and `diff_target`;
        the summary lines and the settings follow, as `upload` prints them. The server then says
        whether it already holds that change (`upload_needed: false`), and the upload is skipped.
        `--pr` is a pull request: the server fetches its diff, so none is worked out here.
        `--author` adds an `author=<GitHub login>` line (empty when it cannot be told).

`--guide <name>` (on `start` and `upload`): when settings files apply to the change, the part
of the skill that says what to do with them (`resources/skills/<name>.md`) is printed after
them, under `settings-guide:`. A repository with no settings never reads it.

    CE_UPLOAD_TOKEN=<token> python cloudaeye_session.py upload --session <id> --url <upload_url>
            [--target <branch>] [--scope <path>] [--settings] [--key-url <url>]
        Diff the working tree against the fork point off the target branch and upload it.
        `--settings` also prints the settings that apply; `--review` does that, leaves out the
        paths the settings never review, and sends the repository's own LLM key when one is set.

`upload` prints the lines every skill reads:

    session_id=<id> base_source=fork_point|head base_age=<age>
    diff_bytes=<n> diff_files=<n> total_files=<n> scope=<path or -> skipped_by_settings=<n> upload_http=<code>
        diff_unchanged=true|false|unknown        (on the same line: the server already had this change)
    changed_files=<up to 20 paths, comma-separated> (+<n> more)
    settings:                                   (only with --settings)
    <the JSON `cloudaeye_config.py effective` prints>

or `cloudaeye_error=<reason>` and exit 1. Three things it is careful about:

- **The developer's git index is never touched.** New files have to be in the diff, so they are
  marked intent-to-add in a temporary copy of the index (`GIT_INDEX_FILE`), which is deleted.
- **CloudAEye's own files are not the change**: an untracked `.OWNERS.md` (written by
  `/cloudaeye:assign-reviewer`) is left out; `.cloudaeye/` ignores itself.
- **Tokens come from the environment** (`CE_UPLOAD_TOKEN`, `CE_KEY_TOKEN`), never the command line,
  and are never printed.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

HEADER = "X-Upload-Token"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_QUIET = {"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "GIT_ASKPASS": "echo"}
OWNERS_EXCLUDE = ":(exclude,glob)**/.OWNERS.md"
NAMES_SHOWN = 20            # changed files named on the summary; the rest are counted
STATE = "state.json"        # under .cloudaeye/session/: what the last upload was cut against. No secret.


class SessionError(RuntimeError):
    pass


def _git(root: Path, *args: str, env: dict[str, str] | None = None, check: bool = True, timeout: int = 120) -> bytes:
    try:
        done = subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=timeout,
                              env={**os.environ, **_QUIET, **(env or {})})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SessionError("git_command_failed") from exc
    if check and done.returncode != 0:
        raise SessionError("git_command_failed")
    return done.stdout if done.returncode == 0 else b""


def _text(raw: bytes) -> str:
    return raw.decode("utf-8", "replace").strip()


def repository_root() -> Path:
    try:
        done = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SessionError("not_a_git_repo") from exc
    if done.returncode != 0:
        raise SessionError("not_a_git_repo")
    return Path(_text(done.stdout))


def workspace(root: Path) -> Path:
    home = root / ".cloudaeye"
    (home / "session").mkdir(parents=True, exist_ok=True)
    (home / ".gitignore").write_text("*\n", encoding="utf-8")
    return home


def allowed_url(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme == "https":
        return bool(parts.hostname)
    return parts.scheme == "http" and (parts.hostname or "") in _LOCAL_HOSTS


def safe_target(target: str) -> str:
    return target if re.fullmatch(r"[A-Za-z0-9._/][A-Za-z0-9._/-]*", target or "") else ""


def safe_scope(scope: str) -> str:
    scope = (scope or "").strip()
    if not scope:
        return ""
    if ".." in scope or scope.startswith(("/", "~", "-")) or re.match(r"^[A-Za-z]:", scope):
        raise SessionError("scope_outside_repo")
    return scope


def baseline(root: Path, target: str) -> tuple[str, str, str]:
    """(base sha, where it came from, how old the target's tip is)."""
    head = _text(_git(root, "rev-parse", "HEAD"))
    base = ""
    if target:
        if not _git(root, "rev-parse", "--verify", "-q", f"origin/{target}", check=False):
            _git(root, "-c", "credential.helper=", "fetch", "-q", "origin", target, check=False)
        base = _text(_git(root, "merge-base", f"origin/{target}", "HEAD", check=False))
    age = _text(_git(root, "log", "-1", "--format=%cr", f"origin/{target}", check=False)) if target else ""
    if base:
        return base, "fork_point", age or "unknown"
    return head, "head", age or "unknown"


def temporary_index(root: Path, scratch: Path) -> dict[str, str]:
    """A copy of the index with new files marked intent-to-add: `git diff` then shows them, and
    the developer's own index is as they left it."""
    index = scratch / "index"
    real = _text(_git(root, "rev-parse", "--git-path", "index"))
    source = Path(real) if os.path.isabs(real) else root / real
    if source.exists():
        # copy2, for the timestamp: git trusts a file whose size and time match the index only when
        # the index is newer than the file. A copy stamped "now" made an edit in the same second as
        # the last commit, to a same-sized file, invisible to the diff.
        shutil.copy2(source, index)
    env = {"GIT_INDEX_FILE": str(index)}
    _git(root, "add", "--intent-to-add", "--", ".", OWNERS_EXCLUDE, env=env, check=False)
    return env


def _config(root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    script = Path(__file__).with_name("cloudaeye_config.py")
    try:
        done = subprocess.run([sys.executable, str(script), *args], cwd=root, capture_output=True, timeout=120,
                              env={**os.environ, **(env or {})})
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout.decode("utf-8", "replace")


def skip_patterns(root: Path) -> list[str]:
    out = []
    for line in _config(root, "skip").splitlines():
        line = line.strip()
        if line and ".." not in line and not line.startswith(("/", "~")):
            out.append(line)
    return out


def post_diff(url: str, token: str, diff: bytes, base: str) -> tuple[int, str]:
    """The HTTP status, and whether the server already had this exact change: `true`, `false`, or
    `unknown` when it did not say. The skills read the second to send no new intent for the same
    change, which is what lets the server answer it from what it stored."""
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="base_sha"\r\n\r\n{base}\r\n'.encode("utf-8"),
        (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="session.diff"\r\n'
         "Content-Type: application/octet-stream\r\n\r\n").encode("utf-8"),
        diff, f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    request = urllib.request.Request(url, data=b"".join(parts), method="POST", headers={
        HEADER: token, "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            status, body = int(response.status), response.read(4096)
    except urllib.error.HTTPError as exc:
        return int(exc.code), "unknown"
    except (urllib.error.URLError, OSError):
        return 0, "unknown"
    try:
        said = json.loads(body.decode("utf-8", "replace")).get("diff_unchanged")
    except (ValueError, AttributeError):
        said = None
    return status, ("true" if said is True else "false" if said is False else "unknown")


def remembered(home: Path) -> str | None:
    """The branch the last upload from this checkout was cut against (`""` when the repository had none and
    the baseline was HEAD), or `None` when nothing has been uploaded from here yet."""
    try:
        doc = json.loads((home / "session" / STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    target = doc.get("target") if isinstance(doc, dict) else None
    return target if isinstance(target, str) and (not target or safe_target(target)) else None


def remember(home: Path, target: str) -> None:
    try:
        (home / "session" / STATE).write_text(json.dumps({"target": target}), encoding="utf-8")
    except OSError:
        pass                                # the next command uploads, as it always did


@contextlib.contextmanager
def change(root: Path, home: Path, target: str, scope: str, review: bool):
    """The change as it is uploaded: the diff against the fork point off `target`, narrowed to `scope` and,
    for a review, without the paths the settings never review. One function for `upload` and `start`: the
    server skips an upload only for the exact bytes it holds, so the two must cut the same diff. It yields
    while the temporary index is alive, which `settings_text` reads through."""
    base, source, age = baseline(root, safe_target(target))
    scratch = Path(tempfile.mkdtemp(prefix="cloudaeye-"))
    try:
        env = temporary_index(root, scratch)
        skip = skip_patterns(root) if review else []
        paths = [scope or ".", *(f":(exclude){p}" for p in skip)]
        diff = _git(root, "diff", base, "--", *paths, env=env)
        (home / "session" / "session.diff").write_bytes(diff)
        files = _git(root, "diff", "--name-only", base, "--", *paths, env=env)
        in_scope = len(_text(_git(root, "diff", "--name-only", base, "--", scope or ".", env=env)).splitlines())
        total = len(_text(_git(root, "diff", "--name-only", base, env=env)).splitlines())
        listed = scratch / "files.txt"
        listed.write_bytes(files)
        names = _text(files).splitlines()
        scoped = len(names)
        yield SimpleNamespace(root=root, base=base, source=source, age=age, diff=diff, env=env, listed=listed,
                              counts=f"diff_bytes={len(diff)} diff_files={scoped} total_files={total} "
                                     f"scope={scope or '-'} skipped_by_settings={in_scope - scoped}",
                              # the file list a skill may need, so none runs a git command of its own for it
                              names="changed_files=" + ", ".join(names[:NAMES_SHOWN])
                                    + (f" (+{scoped - NAMES_SHOWN} more)" if scoped > NAMES_SHOWN else ""))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def settings_text(c, review: bool, key_url: str = "") -> str:
    """The settings that apply to the changed files, as JSON. A review also sends the repository's own LLM
    key to `key_url`, when its settings name one and an address was given."""
    send = ["--send-key", key_url if allowed_url(key_url or "") else ""] if review else []
    out = _config(c.root, "effective", *send, "--files", str(c.listed), env=c.env).strip()
    lines = out.splitlines()               # a Windows child writes CRLF; print one ending
    return chr(10).join(lines) if lines else '{"error": "the settings could not be read"}'


def settings_guide(text: str, name: str) -> str:
    """`settings-guide:` and the part of a skill that says what to do with the team's settings, or `""` when
    there are none to act on: no file applied, no rule, nothing a file could not read."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name or ""):
        return ""
    try:
        doc = json.loads(text)
    except ValueError:
        return ""
    if not isinstance(doc, dict) or not (doc.get("applied") or doc.get("rules") or doc.get("problems")
                                         or doc.get("pending") or "error" in doc or doc.get("fetched") is False):
        return ""
    try:
        guide = (Path(__file__).resolve().parents[1] / "resources" / "skills" / f"{name}.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    return "settings-guide:" + chr(10) + guide.rstrip()


def _names_a_key(text: str) -> bool:
    """The settings name an API key of the repository's own. It travels with the upload and is kept for a
    day, so a change whose settings name one is always uploaded."""
    try:
        doc = json.loads(text) if text else {}
    except ValueError:
        return False
    review = doc.get("review") if isinstance(doc, dict) else None
    return isinstance(review, dict) and "api_key" in review


def start_command(args: argparse.Namespace) -> int:
    import repository_preflight

    scope = safe_scope(args.scope)
    try:
        who = repository_preflight.identity()
    except repository_preflight.PreflightError as exc:
        raise SessionError(str(exc)) from exc
    start = {"repo": who["repo_full"], "branch": who["branch"], "head": who["head"],
             "provider": who["provider"], "repo_url": who["repo_url"]}
    lines: list[str] = []
    root = repository_root()
    home = workspace(root)
    target = None if args.pr else remembered(home)
    if target is not None:
        with change(root, home, target, scope, args.review) as c:
            text = settings_text(c, args.review) if args.settings or args.review else ""
            if not _names_a_key(text):
                start.update({"diff_sha256": hashlib.sha256(c.diff).hexdigest(), "diff_base": c.base,
                              "diff_target": target})
                lines = [f"base_source={c.source} base_age={c.age}", c.counts, c.names] + (
                    ["settings:", text] if text else [])
                if text and settings_guide(text, args.guide):
                    lines.append(settings_guide(text, args.guide))
    print(json.dumps(start, separators=(",", ":")))
    if args.author:
        import cloudaeye_cli

        print(f"author={cloudaeye_cli.github_login()}")
    for line in lines:
        print(line)
    return 0


def head_command() -> int:
    root = repository_root()
    workspace(root)
    remote = _text(_git(root, "config", "--get", "remote.origin.url", check=False))
    repo = re.sub(r"\.git$", "", remote.rstrip("/").replace(":", "/").rsplit("/", 1)[-1]) or root.name
    print(json.dumps({"repo": repo, "branch": _text(_git(root, "rev-parse", "--abbrev-ref", "HEAD")),
                      "head": _text(_git(root, "rev-parse", "HEAD"))}))
    return 0


def upload_command(args: argparse.Namespace) -> int:
    token = os.environ.get("CE_UPLOAD_TOKEN", "").strip()
    if not re.fullmatch(r"[0-9A-Fa-f-]+", args.session or ""):
        raise SessionError("bad_session")
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", token):
        raise SessionError("bad_upload_token")
    if not allowed_url(args.url):
        raise SessionError("insecure_url")
    scope = safe_scope(args.scope)
    root = repository_root()
    home = workspace(root)
    target = safe_target(args.target)
    with change(root, home, target, scope, args.review) as c:
        status, unchanged = post_diff(args.url, token, c.diff, c.base)  # an empty diff too: it replaces a stale one
        if status == 200:
            remember(home, target)          # the next command's `start` can then name this change before uploading
        print(f"session_id={args.session} base_source={c.source} base_age={c.age}")
        print(f"{c.counts} upload_http={status} diff_unchanged={unchanged}")
        print(c.names)
        if args.settings or args.review:
            # a review also sends the repository's own LLM key, when its settings name one
            print("settings:")
            text = settings_text(c, args.review, args.key_url if args.review else "")
            print(text)
            if settings_guide(text, args.guide):
                print(settings_guide(text, args.guide))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("head")
    st = sub.add_parser("start")
    st.add_argument("--scope", default="")
    st.add_argument("--settings", action="store_true", help="print the settings that apply to the changed files")
    st.add_argument("--review", action="store_true", help="a review: leave out the paths the settings never review")
    st.add_argument("--pr", action="store_true", help="a pull request: the server fetches its diff")
    st.add_argument("--author", action="store_true", help="also print author=<the developer's GitHub login>")
    st.add_argument("--guide", default="", help="print this guide after settings that apply")
    up = sub.add_parser("upload")
    up.add_argument("--session", required=True)
    up.add_argument("--url", required=True)
    up.add_argument("--target", default="")
    up.add_argument("--scope", default="")
    up.add_argument("--settings", action="store_true", help="print the settings that apply to the changed files")
    up.add_argument("--review", action="store_true",
                    help="a review: also leave out the paths the settings never review, and send the LLM key")
    up.add_argument("--key-url", default="")
    up.add_argument("--guide", default="", help="print this guide after settings that apply")
    args = parser.parse_args(argv)
    try:
        if args.command == "head":
            return head_command()
        return start_command(args) if args.command == "start" else upload_command(args)
    except SessionError as exc:
        print(f"cloudaeye_error={exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
