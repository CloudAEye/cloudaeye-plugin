#!/usr/bin/env python3
"""Prepare and upload the change a CloudAEye command reviews. One script, so no skill carries the shell.

    python cloudaeye_session.py head
        Print {"branch": ..., "head": ...} for start_session, and make `.cloudaeye/` (git-ignored).

    CE_UPLOAD_TOKEN=<token> python cloudaeye_session.py upload --session <id> --url <upload_url>
            [--target <branch>] [--scope <path>] [--settings] [--key-url <url>]
        Diff the working tree against the fork point off the target branch and upload it.
        `--settings` also prints the settings that apply; `--review` does that, leaves out the
        paths the settings never review, and sends the repository's own LLM key when one is set.

`upload` prints the lines every skill reads:

    session_id=<id> base_source=fork_point|head base_age=<age>
    diff_bytes=<n> diff_files=<n> total_files=<n> scope=<path or -> skipped_by_settings=<n> upload_http=<code>
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
from urllib.parse import urlsplit

HEADER = "X-Upload-Token"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_QUIET = {"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "GIT_ASKPASS": "echo"}
OWNERS_EXCLUDE = ":(exclude,glob)**/.OWNERS.md"


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


def post_diff(url: str, token: str, diff: bytes, base: str) -> int:
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
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except (urllib.error.URLError, OSError):
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
    base, source, age = baseline(root, safe_target(args.target))
    scratch = Path(tempfile.mkdtemp(prefix="cloudaeye-"))
    try:
        env = temporary_index(root, scratch)
        skip = skip_patterns(root) if args.review else []
        paths = [scope or ".", *(f":(exclude){p}" for p in skip)]
        diff = _git(root, "diff", base, "--", *paths, env=env)
        (home / "session" / "session.diff").write_bytes(diff)
        files = _git(root, "diff", "--name-only", base, "--", *paths, env=env)
        in_scope = len(_text(_git(root, "diff", "--name-only", base, "--", scope or ".", env=env)).splitlines())
        total = len(_text(_git(root, "diff", "--name-only", base, env=env)).splitlines())
        listed = scratch / "files.txt"
        listed.write_bytes(files)
        scoped = len(_text(files).splitlines())
        status = post_diff(args.url, token, diff, base)     # an empty diff too: it replaces a stale one
        print(f"session_id={args.session} base_source={source} base_age={age}")
        print(f"diff_bytes={len(diff)} diff_files={scoped} total_files={total} scope={scope or '-'} "
              f"skipped_by_settings={in_scope - scoped} upload_http={status}")
        if args.settings or args.review:
            # a review also sends the repository's own LLM key, when its settings name one
            key_url = args.key_url if args.review and allowed_url(args.key_url or "") else ""
            print("settings:")
            send = ["--send-key", key_url] if args.review else []
            out = _config(root, "effective", *send, "--files", str(listed), env=env).strip()
            lines = out.splitlines()               # a Windows child writes CRLF; print one ending
            print(chr(10).join(lines) if lines else '{"error": "the settings could not be read"}')
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("head")
    up = sub.add_parser("upload")
    up.add_argument("--session", required=True)
    up.add_argument("--url", required=True)
    up.add_argument("--target", default="")
    up.add_argument("--scope", default="")
    up.add_argument("--settings", action="store_true", help="print the settings that apply to the changed files")
    up.add_argument("--review", action="store_true",
                    help="a review: also leave out the paths the settings never review, and send the LLM key")
    up.add_argument("--key-url", default="")
    args = parser.parse_args(argv)
    try:
        return head_command() if args.command == "head" else upload_command(args)
    except SessionError as exc:
        print(f"cloudaeye_error={exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
