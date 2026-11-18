---
name: create-owners
description: Write .OWNERS.md files for this repository from its git history — who writes each part of the code, with their share and the lead contributor — at the root (or a folder you name) and in every sub-folder down to three levels whose people differ from the rest. Leaves a Teams section for people to fill in. Git blame runs on your machine and only its line counts reach CloudAEye; it writes in your working tree and never commits or pushes.
when_to_use: Use when the user wants to set up or refresh code ownership, create .OWNERS.md files, or prepare the repository for /cloudaeye:assign-reviewer. Not for choosing a reviewer.
argument-hint: "[folder] [--depth N]"
allowed-tools: Read, Grep, Glob, LS
---

## What leaves your machine

`git blame` runs here, on each text file under the folder. Only its line counts go to
CloudAEye: how many lines each author wrote in each file and when, under the author's name and
email address as git records them. Never a line of code and never a commit message. CloudAEye
keeps a digest of each address, never the address, and the line counts only for this command.
It works out the files and answers with what to write; the files are written here, in your
working tree. Nothing is written on GitHub, and this command costs no credits.

## What it writes

Every `.OWNERS.md` has two sections:

- **Contributors**, measured from `git blame` over lines written in the last 12
  months: each person's share of the folder's code and the **lead contributor**,
  the largest share. A later run rewrites this section, and only when a share
  moved 5 points or someone joined or left the list.
- **Teams**, written by people: one line per team, its lead marked —
  `- Payments: @alice (lead), @bob`. It starts blank. A run never removes or
  rewrites a line of it.

**Where files go.** The folder given (default: the repository root) always gets
one. Every folder down to `--depth` levels below it (default 3) gets its own only
when the people who wrote it differ enough from the rest of the area around it.
A folder that already has a `.OWNERS.md` keeps it; a file in the older
`Lead Maintainer:` format is left as it is.

**The name starts with a dot**, so the file stays out of directory listings.
Files from before 9 Nov 2026 are called `OWNERS.md`: each one is renamed
`.OWNERS.md`, keeping its Teams lines, and then refreshed like any other.
CloudAEye no longer reads the old name.

## Steps

1. Parse `$ARGUMENTS`: an optional folder path and an optional `--depth N`
   (a whole number, 0–6). Anything else: say what is supported and stop.

2. Set up the session.

   Find the repository with this one read-only command. This skill runs no script, so Claude Code
   asks before the first run of a command it has not been allowed:

   ```bash
   git rev-parse --show-toplevel HEAD --abbrev-ref HEAD --is-shallow-repository && git remote get-url origin
   ```

   It prints five lines: `TOP` (the repository's folder), `HEAD`, `BRANCH`, `SHALLOW` (`true` or
   `false`) and `ORIGIN`. An error (not a Git repository, no `origin` remote): stop and say
   CloudAEye needs a Git repository with a GitHub, GitLab or Bitbucket remote. `FOLDER` is the
   folder from step 1 as a path from `TOP`, with `/` between names, or `.` for the root; one that
   is not inside `TOP`: say so and stop.

   Then call `mcp__plugin_cloudaeye_cloudaeye__start_session` with `repo_url` = `ORIGIN`, `provider`
   (`github` for github.com, `bitbucket` for bitbucket.org, `gitlab` for a GitLab host), `branch` =
   `BRANCH` and `head` = `HEAD`, and keep the answer as `SESSION`.

   - `SESSION.gate` is `repository`: the repository is not connected to CloudAEye yet. Read
     `${CLAUDE_PLUGIN_ROOT}/resources/skills/connect-repository.md` and follow it.
   - The tool is unavailable, or `status` is `error`: stop and tell the user to authenticate CloudAEye through `/mcp`.

3. **The files already there.** Glob `**/.OWNERS.md` and `**/OWNERS.md` with `TOP` as the path.
   When any are found, Read them all in one turn and keep `OWNERS`: each path relative to `TOP`,
   with `/` between names, mapped to its text. Their Teams lines are kept, and a folder that has
   one keeps it.

4. **Count the blame.** Run this one command, writing in `<FOLDER>`, `<UPLOAD_URL>` and
   `<UPLOAD_TOKEN>` (from `SESSION`). It writes only under `.cloudaeye/` (which ignores itself).
   It runs in `TOP`: when that is not the folder Claude Code is working in, put `cd '<TOP>' && `
   in front of it. It runs one `git blame` a file, so give it the Bash tool's longest timeout
   (10 minutes): about a minute for 300 files. If even that runs out, run the command on a
   folder instead.

   ```bash
   mkdir -p .cloudaeye && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Upload-Token:%s"\n' '<UPLOAD_URL>' '<UPLOAD_TOKEN>' | tee .cloudaeye/upload.curl && git grep -I -l -z -e '' -- '<FOLDER>' ':(exclude,glob)**/vendor/**' ':(exclude,glob)**/node_modules/**' ':(exclude,glob)**/*.json' ':(exclude,glob)**/*.lock' | xargs -0 -n1 sh -c 'printf "cloudaeye-file %s\n" "$1" && git blame --incremental -w -M -C HEAD -- "$1" 2>/dev/null' blame | grep -E '^(cloudaeye-file |[0-9a-f]{40,64} [0-9]+ [0-9]+ [0-9]+$|author |author-mail |author-time )' | curl -sS --fail-with-body -K .cloudaeye/upload.curl -F 'blame=@-;filename=blame.txt'
   ```

   It prints the upload's settings file, then the server's answer as JSON. Never print the
   upload token.

   | what came back | what to do with it |
   |---|---|
   | `curl: (22)` and an error | The counts never reached CloudAEye. Report the error and stop. |
   | `blame_files` is `0` | No text file under `FOLDER` has any history to count. Say so and stop. |
   | `blame_files` | How many files were counted. Go on. |

5. **Work out the files.** Call `mcp__plugin_cloudaeye_cloudaeye__create_owners` with
   `session_id` = `SESSION.session_id`, `path` = `FOLDER` (empty for `.`), `depth` when one was
   given, `owners` = `OWNERS` when there are any, `head` = `HEAD` and `shallow` = `true` when
   `SHALLOW` is `true`. On `status: error`, report `error` and stop.

6. **Write them.** First the `renames`, when there are any, with one command that moves each
   `from` to its `to` (paths from `TOP`; put `cd '<TOP>' && ` in front when needed):

   ```bash
   mv '<from>' '<to>' && mv '<from>' '<to>'
   ```

   Then each of `writes`, at `TOP` + its `path`: when it has `edits`, apply each one with Edit
   (`old_string` → `new_string`), in order; otherwise Write its `text` as the whole file. Use the
   text exactly as given, and write nothing else.

7. Report, briefly:
   - a table of `owners_files`: path, `action` (created, contributors updated,
     unchanged, team added, older format left as it is) and the lead contributor,
     with *renamed from OWNERS.md* beside a row that has `renamed_from`;
   - `old_names_left`: folders that have both names, where the old
     `OWNERS.md` was left as it was; say it can be deleted once its Teams lines
     are in `.OWNERS.md`;
   - `problems`, when there are any, once;
   - when `shallow` is true: the history is shallow, so the shares cover only
     the commits present; suggest `git fetch --unshallow` and a rerun;
   - `needs_a_handle`: git authors with no GitHub username the history could
     show. They are written as comments, not as contributors.

8. **Handles.** If `needs_a_handle` is not empty, ask once, in one message, for
   the GitHub username of each name (the user may skip any). Call `create_owners`
   again with the same arguments plus `aliases`, each git name mapped to its
   username, and `owners` as the files are now: each write's `text` at its `path`,
   and a renamed file at its `to`. No new upload: CloudAEye kept the counts. Apply
   the answer as in step 6.

9. **Teams — optional, and only about the person running it.** Ask once:
   *Which team are you in on this project, and who leads it? (optional — skip
   to leave Teams blank)*. Their own username is `runner.login`; if it is
   null and they answered, ask for it. Then call `create_owners` again as in
   step 8, adding `team`, `team_lead` (the lead's username) and `members` (a list
   holding their own username), and apply the answer as in step 6. Never fill in
   anyone else's team; people add their own over time.

10. End with: the files are in the working tree; review them with `git diff`
    and commit them through a pull request like any other change (a renamed
    file shows as `OWNERS.md` deleted and `.OWNERS.md` new until both are
    staged; `git add -A` on them records the rename). CloudAEye
    reads them from the target branch, so they take effect once merged.

## Notes

- Never write `.OWNERS.md` yourself or edit the Contributors section by hand:
  the numbers come from CloudAEye, the same way every time. Write only what
  `writes` holds.
- No email address ever goes into the file. A name without a username stays a
  comment.
- Re-running is safe: it changes Contributors only when the numbers moved, and
  never touches Teams.
- `/cloudaeye:assign-reviewer` reads these files from the target branch, and
  sends the ones in your working tree until they are merged.
- If `create_owners` is unavailable (MCP not connected), warn and stop — never
  work out shares yourself from `git blame` or `git log`.
