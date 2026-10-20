---
name: create-owners
description: Write OWNERS.md files for this repository from its git history — who writes each part of the code, with their share and the lead contributor — at the root (or a folder you name) and in every sub-folder down to three levels whose people differ from the rest. Leaves a Teams section for people to fill in. Runs locally with Git and Python only; never commits or pushes.
when_to_use: Use when the user wants to set up or refresh code ownership, create OWNERS.md files, or prepare the repository for /cloudaeye:assign-reviewer. Not for choosing a reviewer.
argument-hint: "[folder] [--depth N]"
allowed-tools: ["Bash", "Read"]
---

## Local only

This command uses Git and Python on this machine and nothing else: no CloudAEye
call, no network, no initialization gate, no model. It writes files in the
working tree and never commits, pushes or opens a pull request.

## What it writes

Every `OWNERS.md` has two sections:

- **Contributors**, measured from `git blame` over lines written in the last 12
  months: each person's share of the folder's code and the **lead contributor**,
  the largest share. The script rewrites this section on a later run, and only
  when a share moved 5 points or someone joined or left the list.
- **Teams**, written by people: one line per team, its lead marked —
  `- Payments: @alice (lead), @bob`. It starts blank. The script never removes
  or rewrites a line of it.

**Where files go.** The folder given (default: the repository root) always gets
one. Every folder down to `--depth` levels below it (default 3) gets its own only
when the people who wrote it differ enough from the rest of the area around it.
A folder that already has an `OWNERS.md` keeps it; a file in the older
`Lead Maintainer:` format is left as it is.

## Steps

1. Parse `$ARGUMENTS`: an optional folder path and an optional `--depth N`
   (a whole number, 0–6). Anything else: say what is supported and stop.

2. Run the script from the repository:

```bash
for c in python python3 py; do command -v "$c" >/dev/null 2>&1 && "$c" -c "" 2>/dev/null && { PY=$c; break; }; done
[ -n "$PY" ] || { echo "cloudaeye_error=python_not_found"; exit 1; }
"$PY" "${CLAUDE_PLUGIN_ROOT}/scripts/create_owners.py" <folder if given> <--depth N if given>
```

   It prints one JSON object. On `"status": "error"`, report `error` and stop.
   A large repository can take a few minutes (one `git blame` a file).

3. Report, briefly:
   - a table of `owners_files`: path, `action` (created, contributors updated,
     unchanged, older format left as it is) and the lead contributor;
   - when `shallow` is true: the history is shallow, so the shares cover only
     the commits present; suggest `git fetch --unshallow` and a rerun;
   - `needs_a_handle`: git authors with no GitHub username the history could
     show. They are written as comments, not as contributors.

4. **Handles.** If `needs_a_handle` is not empty, ask once, in one message, for
   the GitHub username of each name (the user may skip any). Rerun the same
   command with one `--alias "Git Name=username"` per answer.

5. **Teams — optional, and only about the person running it.** Ask once:
   *Which team are you in on this project, and who leads it? (optional — skip
   to leave Teams blank)*. Their own username is `runner.login`; if it is
   empty and they answered, ask for it. Then rerun the same command with
   `--team "<team>" --team-lead <lead username> --member <their username>`.
   Never fill in anyone else's team; people add their own over time.

6. End with: the files are in the working tree; review them with `git diff`
   and commit them through a pull request like any other change. CloudAEye
   reads them from the target branch, so they take effect once merged.

## Notes

- Never write `OWNERS.md` yourself or edit the Contributors section by hand:
  the numbers come from the script, the same way every time.
- No email address ever goes into the file. A name without a username stays a
  comment.
- Re-running is safe: it changes Contributors only when the numbers moved, and
  never touches Teams.
- `/cloudaeye:assign-reviewer` runs this at the root on its own when the target
  branch has no `OWNERS.md`, and uses the files from the working tree until they
  are merged.
