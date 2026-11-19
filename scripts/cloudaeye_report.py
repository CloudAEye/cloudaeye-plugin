#!/usr/bin/env python3
"""Save a CloudAEye command's whole report to a file in the repository.

    CE_REPORT_TOKEN=<token> python cloudaeye_report.py --url <url> --name <command>

A finished command answers with a short text for the terminal and `report` (`url`, `token`,
`name`). This fetches the whole report (pictures, collapsed sections, every command's output)
with that read-only token and writes it to `.cloudaeye/reports/<name>.md`, so it reaches the
developer's disk without the coding agent reading or re-typing it.

Prints one line: `report_path=<path> report_bytes=<n>`, or `report_error=<reason>` and exits 1.
When the server serves it, the same report as a web page with its diagrams drawn is saved beside it
(`.cloudaeye/reports/<name>.html`) and a second line says where: `page_path=<path> page_url=<file URL>`.
A terminal draws no mermaid; a browser does. The token is read from the environment, never from the
command line, and never printed.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

HEADER = "X-Report-Token"
NAME = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
#: A pull-request comment is at most 65,536 characters; nothing a report holds is near this.
MAX_BYTES = 4 * 1024 * 1024
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class ReportError(RuntimeError):
    pass


def allowed_url(url: str) -> bool:
    """https anywhere, plain http only to this machine: the token must not cross a network in the clear."""
    parts = urlsplit(url)
    if parts.scheme == "https":
        return bool(parts.hostname)
    return parts.scheme == "http" and (parts.hostname or "") in _LOCAL_HOSTS


def repository_root(start: str | None = None) -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start or None, check=True,
                             capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReportError("not_a_git_repo") from exc
    return Path(out.stdout.strip())


def fetch(url: str, token: str, *, kind: str = "") -> bytes:
    """The report at ``url``; with ``kind`` (``text/html``), only when the server answers with that type."""
    request = urllib.request.Request(url, headers={HEADER: token}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if kind and not str(response.headers.get("Content-Type") or "").startswith(kind):
                raise ReportError("not_served")          # a server from before the page answers markdown
            body = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise ReportError({401: "token_refused", 404: "no_report"}.get(exc.code, f"http_{exc.code}")) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise ReportError("unreachable") from exc
    if len(body) > MAX_BYTES:
        raise ReportError("too_large")
    if not body.strip():
        raise ReportError("empty")
    return body


def page_url(url: str) -> str:
    """The same report as a web page, its diagrams drawn: the report route's ``?format=html``."""
    return url + ("&" if "?" in url else "?") + "format=html"


def save(root: Path, name: str, body: bytes, suffix: str = ".md") -> Path:
    home = root / ".cloudaeye"
    target = home / "reports" / f"{name}{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    ignore = home / ".gitignore"
    if not ignore.exists():                      # the folder is CloudAEye's working space, never the change
        ignore.write_text("*\n", encoding="utf-8")
    partial = target.with_name(target.name + ".part")
    partial.write_bytes(body)
    os.replace(partial, target)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--root", default="", help="repository root (default: the current repository)")
    args = parser.parse_args(argv)
    try:
        token = os.environ.get("CE_REPORT_TOKEN", "").strip()
        if not NAME.match(args.name):
            raise ReportError("bad_name")
        if not allowed_url(args.url):
            raise ReportError("insecure_url")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{20,2048}", token):
            raise ReportError("bad_token")
        root = Path(args.root) if args.root else repository_root()
        target = save(root, args.name, fetch(args.url, token))
    except ReportError as exc:
        print(f"report_error={exc}")
        return 1
    try:
        shown = target.relative_to(root).as_posix()
    except ValueError:
        shown = str(target)
    print(f"report_path={shown} report_bytes={target.stat().st_size}")
    # the same report as a page with its diagrams drawn, which a terminal cannot show; best effort,
    # and a server from before the page has none, so nothing is said
    try:
        page = save(root, args.name, fetch(page_url(args.url), token, kind="text/html"), ".html")
    except ReportError:
        return 0
    try:
        page_shown = page.relative_to(root).as_posix()
    except ValueError:
        page_shown = str(page)
    print(f"page_path={page_shown} page_url={page.resolve().as_uri()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
