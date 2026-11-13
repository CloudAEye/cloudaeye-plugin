#!/usr/bin/env python3
"""The plugin's shell steps, behind one command (`sh scripts/cae <step> ...`).

    cae start [--scope PATH] [--settings] [--review] [--pr]
                                          what `start_session` is called with: the repository, branch and
                                          HEAD, and the change itself when it can be named before an upload
    cae guide <name>                      a part of a skill that is read only when it is needed
    cae preflight [--branch B]            the repository's provider, URL, branch and HEAD
    cae head                              repo, branch and HEAD only (no provider check)
    cae upload '<start_session answer>' [--scope PATH] [--settings] [--review]
                                          diff the working tree and upload it
    cae pr-settings '<start_session answer>' [--review] [--guide NAME]
                                          a pull request's settings, read at its target branch
    cae report <name> '<result.report>'   save a command's whole report to .cloudaeye/reports/
    cae login                             the developer's GitHub login, when it can be told
    cae open '<url>'                      open CloudAEye's connect page in the browser
    cae config <args...>                  cloudaeye_config.py, as it is
    cae config-start                      the repository and the settings files it already has
    cae config-file sync-rules|seed '<tool answer>'
                                          cloudaeye_config.py with a tool's answer as its --file
    cae owners <args...>                  create_owners.py, as it is

Steps that follow a tool call take that tool's own answer as one quoted JSON argument, so a
skill never picks fields out of it and nothing has to be set in the environment first. Each
prints a few `key=value` lines or JSON, or `cloudaeye_error=<reason>` and exits 1.

Why one command: a skill pre-approves `sh .../scripts/cae *`, and a developer is then never asked
to approve a shell step. A loop, a `VAR=value` prefix or a chained command would bring the
prompt back.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _fail(line: str) -> int:
    print(line)
    return 1


def _answer(text: str) -> dict | None:
    """A tool answer pasted as JSON; MCP wraps some as {"result": "<json>"}."""
    try:
        doc = json.loads(text)
        if isinstance(doc, dict) and isinstance(doc.get("result"), str):
            doc = json.loads(doc["result"])
        return doc if isinstance(doc, dict) else None
    except ValueError:
        return None


def _allowed_url(url: str) -> bool:
    parts = urlsplit(url or "")
    if parts.scheme == "https":
        return bool(parts.hostname)
    return parts.scheme == "http" and (parts.hostname or "") in _LOCAL_HOSTS


def upload(args: list[str]) -> int:
    import cloudaeye_session

    doc = _answer(args.pop(0)) if args else None
    if doc is None:
        return _fail("cloudaeye_error=bad_session_json")
    os.environ["CE_UPLOAD_TOKEN"] = str(doc.get("upload_token") or "")
    os.environ["CE_KEY_TOKEN"] = str(doc.get("key_token") or "")
    return cloudaeye_session.main(["upload", "--session", str(doc.get("session_id") or ""),
                                   "--url", str(doc.get("upload_url") or ""),
                                   "--target", str(doc.get("target_branch") or ""),
                                   "--key-url", str(doc.get("key_url") or ""), *args])


def guide(args: list[str]) -> int:
    """Print `resources/skills/<name>.md`: the branch of a skill that most runs never take. It comes through
    this command so it needs no permission of its own, and costs a turn only on the run that needs it."""
    name = args[0] if args else ""
    path = Path(__file__).resolve().parents[1] / "resources" / "skills" / f"{name}.md"
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) or not path.is_file():
        return _fail("cloudaeye_error=unknown_guide")
    print("(In this guide, `cae <step> ...` is the command this skill already runs — "
          "`sh <plugin>/scripts/cae` — with those arguments, alone in its Bash call.)\n")
    print(path.read_text(encoding="utf-8").rstrip())
    return 0


def pr_settings(args: list[str]) -> int:
    """The settings that apply to a pull request's files, as its target branch has them."""
    import cloudaeye_config

    doc = _answer(args.pop(0)) if args else None
    print("settings:")
    pull = (doc or {}).get("pull_request") or {}
    base = str(pull.get("base") or "")
    files = [str(f.get("path") or f.get("filename") or "") if isinstance(f, dict) else str(f) for f in pull.get("files") or []]
    files = [f for f in files if f and not f.startswith("-")]
    # git's own rules for a branch name, the ones that matter here: no `..`, no leading `/` or `-`
    if not re.fullmatch(r"[A-Za-z0-9._][A-Za-z0-9._/-]*", base) or ".." in base or base.endswith(("/", ".lock")):
        print('{"error": "the target branch is unknown"}')
        return 0
    extra: list[str] = []
    if "--review" in args and _allowed_url(str(doc.get("key_url") or "")):
        os.environ["CE_KEY_TOKEN"] = str(doc.get("key_token") or "")
        extra = ["--send-key", str(doc["key_url"])]
    import contextlib
    import io

    import cloudaeye_session

    held = io.StringIO()
    try:
        with contextlib.redirect_stdout(held):
            code = cloudaeye_config.main(["effective", "--ref", f"origin/{base}", *extra, "--", *files])
        text = held.getvalue().strip()
    except SystemExit:
        code, text = 0, '{"error": "the settings could not be read"}'
    print(text)
    name = args[args.index("--guide") + 1] if "--guide" in args[:-1] else ""
    if cloudaeye_session.settings_guide(text, name):
        print(cloudaeye_session.settings_guide(text, name))
    return code


def report(args: list[str]) -> int:
    import cloudaeye_report

    doc = _answer(args[1]) if len(args) > 1 else None
    if doc is None:
        return _fail("report_error=bad_report_json")
    os.environ["CE_REPORT_TOKEN"] = str(doc.get("token") or "")
    return cloudaeye_report.main(["--url", str(doc.get("url") or ""), "--name", args[0]])


def github_login() -> str:
    """The developer's GitHub login: from the GitHub CLI when it is signed in, else a noreply commit address,
    else `""`."""
    found = ""
    for command in (["gh", "api", "user", "--jq", ".login"], ["git", "config", "user.email"]):
        try:
            out = subprocess.run(command, capture_output=True, text=True, timeout=15).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if command[0] == "git":
            match = re.fullmatch(r"(?:\d+\+)?([A-Za-z0-9-]+)@users\.noreply\.github\.com", out)
            out = match.group(1) if match else ""
        if re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", out or ""):
            found = out
            break
    return found


def login(_args: list[str]) -> int:
    """`author=<login>`, empty when it cannot be told."""
    print(f"author={github_login()}")
    return 0


def open_link(args: list[str]) -> int:
    import webbrowser

    url = args[0] if args else ""
    if not _allowed_url(url):
        return _fail("cloudaeye_error=insecure_integration_url")
    try:
        opened = webbrowser.open(url)
    except Exception:
        opened = False
    print("opened=yes" if opened else f"quick_link={url}")
    return 0


def config_start(_args: list[str]) -> int:
    """What `/cloudaeye:config` needs first: the repository, and the settings files it already has."""
    import contextlib
    import io

    import cloudaeye_config
    import repository_preflight

    try:
        inside = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        inside = False
    if not inside:
        print("repo=not_git")
        return 0
    held = io.StringIO()
    with contextlib.redirect_stdout(held):
        found = repository_preflight.main([]) == 0
    print(held.getvalue().strip() if found else "repo=none")
    held = io.StringIO()
    try:
        with contextlib.redirect_stdout(held):
            cloudaeye_config.main(["show"])
        shown = json.loads(held.getvalue())
        files = ([shown.get("file", "")] if shown.get("exists") else []) + list(shown.get("elsewhere") or [])
    except (SystemExit, ValueError):
        files = []
    print("settings_files=" + " ".join(f for f in files if f))
    return 0


def config_file(args: list[str]) -> int:
    """`config-file sync-rules|seed '<a tool's answer as JSON>'`: the answer goes in as a file."""
    import tempfile

    import cloudaeye_config

    if len(args) < 2 or args[0] not in ("sync-rules", "seed") or _answer(args[1]) is None:
        print('{"error": "expected sync-rules or seed, then the tool answer as JSON"}')
        return 1
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as held:
        json.dump(_answer(args[1]), held)
    try:
        return cloudaeye_config.main([args[0], "--file", held.name, *args[2:]])
    finally:
        os.unlink(held.name)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args.pop(0) if args else ""
    if command == "preflight":
        import repository_preflight

        return repository_preflight.main(args)
    if command == "head":
        import cloudaeye_session

        return cloudaeye_session.main(["head"])
    if command == "start":
        import cloudaeye_session

        return cloudaeye_session.main(["start", *args])
    if command == "config":
        import cloudaeye_config

        return cloudaeye_config.main(args)
    if command == "owners":
        import create_owners

        sys.argv = ["create_owners.py", *args]
        return create_owners.main()
    steps = {"upload": upload, "guide": guide, "pr-settings": pr_settings, "report": report, "login": login, "open": open_link,
             "config-start": config_start, "config-file": config_file}
    if command in steps:
        return steps[command](args)
    return _fail("cloudaeye_error=unknown_command")


if __name__ == "__main__":
    sys.exit(main())
