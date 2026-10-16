#!/usr/bin/env python3
"""Create an OWNERS.md draft from local Git history, without network access."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import sys


def git_metadata_directories(root: Path) -> set[Path]:
    metadata = {(root / ".git").resolve()}
    try:
        paths = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--path-format=absolute",
             "--git-dir", "--git-common-dir"],
            encoding="utf-8", timeout=15, stderr=subprocess.PIPE,
        ).splitlines()
    except subprocess.CalledProcessError:
        if (root / ".git").exists():
            raise ValueError("cannot verify Git metadata directories") from None
        return metadata
    for path in paths:
        metadata.add(Path(path).resolve())
    return metadata


def destination(root: Path, directory: str) -> tuple[Path, str]:
    root = root.resolve(strict=True)
    folder = (root / directory).resolve(strict=True)
    relative = folder.relative_to(root)
    if not folder.is_dir():
        raise ValueError("directory must be an existing directory")
    if any(part.casefold() == ".git" for part in relative.parts):
        raise ValueError("directory must not be Git metadata")
    if any(folder == path or path in folder.parents for path in git_metadata_directories(root)):
        raise ValueError("directory must not be Git metadata")
    target = folder / "OWNERS.md"
    if target.exists() or target.is_symlink():
        raise ValueError("OWNERS.md already exists; edit it manually")
    return target, relative.as_posix()


def contributors(root: Path, directory: str) -> tuple[list[dict], list[str]]:
    git = ["git", "--no-optional-locks", "-C", str(root)]
    warnings = ["Owners are inferred from local Git history. Confirm usernames and contact details before sharing the ownership file."]
    head = subprocess.run(git + ["rev-parse", "--verify", "--quiet", "HEAD"], capture_output=True, timeout=15)
    if head.returncode:
        if head.returncode != 1:
            raise ValueError("cannot read local Git HEAD")
        return [], warnings + ["Repository has no commits; ownership fields were left blank."]
    shallow = subprocess.check_output(git + ["rev-parse", "--is-shallow-repository"], encoding="utf-8", timeout=15).strip()
    if shallow == "true":
        warnings.append("Shallow checkout: suggestions use only the available local history; nothing was fetched.")
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1"}
    revision = head.stdout.decode("ascii").strip()
    tree = subprocess.check_output(
        git + ["ls-tree", "-r", "-z", revision], timeout=30, stderr=subprocess.PIPE, env=env,
    )
    people = {}
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        metadata, path_bytes = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        path = path_bytes.decode("utf-8")
        if mode not in {"100644", "100755"} or kind != "blob" or Path(path).name == "OWNERS.md":
            continue
        if directory != "." and not path.startswith(directory + "/"):
            continue
        blob = subprocess.check_output(git + ["cat-file", "blob", oid], timeout=30, stderr=subprocess.PIPE, env=env)
        if b"\0" in blob[:8000]:
            warnings.append(f"Skipped binary file: {path}")
            continue
        blame = subprocess.check_output(
            git + ["blame", "--line-porcelain", "--encoding=UTF-8", revision, "--", path],
            encoding="utf-8", errors="replace", timeout=60, stderr=subprocess.PIPE, env=env,
        )
        name, email, timestamp = "", "", 0
        for line in blame.split("\n"):
            if line.startswith("author "):
                name = line.removeprefix("author ")
            elif line.startswith("author-mail "):
                email = line.removeprefix("author-mail ").removeprefix("<").removesuffix(">")
            elif line.startswith("author-time "):
                timestamp = int(line.removeprefix("author-time "))
            elif line.startswith("\t"):
                key = email.casefold() or name
                row = people.setdefault(key, {"name": name, "email": email, "lines": 0, "latest": 0})
                row["lines"] += 1
                row["latest"] = max(row["latest"], timestamp)
    ranked = sorted(people.values(), key=lambda row: (-row["lines"], -row["latest"], row["email"], row["name"]))[:3]
    total = sum(person["lines"] for person in people.values())
    for person in ranked:
        person["ownership_percent"] = round(100 * person["lines"] / total, 1)
    if not ranked:
        warnings.append("No committed text lines for this directory; ownership fields were left blank.")
    return ranked, warnings


def create(root: Path, directory: str) -> dict:
    target, relative = destination(root, directory)
    people, warnings = contributors(root, relative)
    identities = []
    for person in people:
        handle = re.fullmatch(
            r"(?:\d+\+)?([A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)@users\.noreply\.github\.com",
            person["email"], re.IGNORECASE,
        )
        identity = f"@{handle[1]}" if handle else f"{person['name']} <{person['email']}>"
        identities.append(" ".join(identity.split()))
    lead = identities[0] if identities else ""
    ownership = "; ".join(
        f"{identity}: {person['ownership_percent']:.1f}% ({person['lines']} lines)"
        for identity, person in zip(identities, people)
    )
    content = ("# Component Ownership\n\n"
               f"- Lead Maintainer: {lead}\n- Team Name: \n"
               f"- Team Members: {', '.join(identities)}\n"
               "- Contact Slack: \n- Contact Email: \n- Risk Level: normal\n"
               f"- Ownership: {ownership}\n\n"
               "Ownership is each author's share of current committed text lines in this directory and its descendants, attributed by git blame. "
               "Includes blank lines and comments; excludes binary files, symlinks, submodules, and OWNERS.md files. "
               "Top three contributors shown; percentages include all contributors.\n")
    # Revalidate the path after reading history; human files always take precedence.
    target, _ = destination(root, relative)
    # Exclusive creation also refuses files created since destination validation.
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    return {"status": "created", "path": str(target), "contributors": people, "warnings": warnings}


def create_all(root: Path) -> dict:
    metadata = git_metadata_directories(root)
    directories = []
    for folder, children, _ in os.walk(root):
        children.sort()
        for name in children[:]:
            child = Path(folder) / name
            if child.is_symlink() or name.casefold() == ".git" or child.resolve() in metadata:
                children.remove(name)
                continue
            ignored = subprocess.run(
                ["git", "-C", str(root), "check-ignore", "-q", "--", child.relative_to(root).as_posix() + "/"],
                capture_output=True, timeout=15,
            )
            if ignored.returncode == 0:
                children.remove(name)
            elif ignored.returncode != 1:
                raise ValueError(f"cannot check ignored directory: {child}")
        directories.append(Path(folder).relative_to(root).as_posix())
    results = []
    for directory in directories:
        target = root / directory / "OWNERS.md"
        if target.exists() or target.is_symlink():
            results.append({"status": "skipped", "path": str(target), "reason": "already exists"})
            continue
        try:
            results.append(create(root, directory))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            results.append({"status": "error", "path": str(target), "error": str(exc)})
    return {"status": "error" if any(r["status"] == "error" for r in results) else "ok", "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", help="existing directory relative to the repository root; omitted means all directories")
    args = parser.parse_args()
    try:
        root = Path(subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], encoding="utf-8", timeout=15,
        ).strip())
        result = create(root, args.directory) if args.directory is not None else create_all(root)
        print(json.dumps(result))
        return 1 if result["status"] == "error" else 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
