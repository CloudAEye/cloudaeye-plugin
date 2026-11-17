---
name: describe
description: Describe the uncommitted changes in this repo — a Change Description heading and an Important Changes bullet list, in plain markdown ready to paste into a PR or a commit message. Trivial diffs short-circuit to one line.
when_to_use: Use when the user asks what changed, for a PR description, a commit message, or a summary of the pending diff.
allowed-tools: Read, Grep, Glob, LS
---

## Queued Result

Submit the analysis once. An answer without `job_id` is the response itself
(report `status: error` and stop). With a `job_id`, call
`mcp__plugin_cloudaeye_cloudaeye__get_job_result(job_id, wait_seconds=110, since=<last progress_id>)`
again and again, with no pause, while `status` is `queued`, `running` or
`retrying`. The server keeps each call open while the job runs.

- Print `⏳ ` + `message` only when `progress_id` changed, exactly as given: no
  job ids, no "polling", no commentary, never a line the server did not send.
- On `completed`, use its `result` as **the response** below, keeping the
  tool's fields. An inner `status: error` is a refusal, not a clean result.
- If the answer carries `next_run`, end with the heading
  `**To get more from the next run**` and each entry as a bullet, exactly as given.
- Stop after 150 calls or 30 minutes and say the job is still running, with its
  id. On `failed` or `error`, report it and stop. Never submit again to check
  progress, and finish the job before any edit, upload or other command on the
  same session.

## Steps

1. Set up the session.

   Find the repository with this one read-only command. This skill runs no script, so Claude Code
   asks before the first run of a command it has not been allowed:

   ```bash
   git rev-parse --show-toplevel HEAD --abbrev-ref HEAD && git remote get-url origin
   ```

   It prints four lines: `TOP` (the repository's folder), `HEAD`, `BRANCH` and `ORIGIN`. An error
   (not a Git repository, no `origin` remote): stop and say CloudAEye needs a Git repository with a
   GitHub, GitLab or Bitbucket remote.

   Then call `mcp__plugin_cloudaeye_cloudaeye__start_session` with `repo_url` = `ORIGIN`, `provider`
   (`github` for github.com, `bitbucket` for bitbucket.org, `gitlab` for a GitLab host), `branch` =
   `BRANCH` and `head` = `HEAD`, and keep the answer as `SESSION`; its `session_id` is the one every
   later call takes.

   - `SESSION.gate` is `repository`: the repository is not connected to CloudAEye yet. Read
     `${CLAUDE_PLUGIN_ROOT}/resources/skills/connect-repository.md` and follow it.
   - The tool is unavailable, or `status` is `error`: stop and tell the user to authenticate CloudAEye through `/mcp`.

   Upload the change with this one command, writing in `<TARGET>` (`SESSION.target_branch`),
   `<UPLOAD_URL>` and `<UPLOAD_TOKEN>` from `SESSION`. It writes only under `.cloudaeye/`
   (which ignores itself) and leaves your git index as it was. It runs in `TOP`: when that is not
   the folder Claude Code is working in, put `cd '<TOP>' && ` in front of it. When `SESSION.target_branch` is
   empty, or the command stops at a `git` error before `curl` runs, read `${CLAUDE_PLUGIN_ROOT}/resources/skills/no-target-branch.md`
   instead.

   ```bash
   git -c credential.helper= fetch -q origin '<TARGET>' 2>/dev/null; mkdir -p .cloudaeye && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Upload-Token:%s"\n' '<UPLOAD_URL>' '<UPLOAD_TOKEN>' | tee .cloudaeye/upload.curl && git rev-parse --git-path index | xargs -I{} cp -p {} .cloudaeye/index && export GIT_INDEX_FILE=.cloudaeye/index && git add -N . && git diff --merge-base 'origin/<TARGET>' --output=.cloudaeye/session.diff -- . && git merge-base HEAD 'origin/<TARGET>' | curl -sS --fail-with-body -K .cloudaeye/upload.curl -F 'base_sha=<-' -F 'file=@.cloudaeye/session.diff'
   ```

   It prints the upload's settings file, then the server's answer as JSON. Never print the upload token.

   | what came back | what to do with it |
   |---|---|
   | `curl: (22)` and an error | The diff never reached the server. Stop; otherwise a stale result can look clean. |
   | `diff_files` is `0` | Nothing pending — report "nothing to describe" and stop. |
   | `changed_files` | The changed paths (up to 20, `more_files` beyond). Take a file list from here, never from a git command of your own. |

   **Say which baseline applied:** the change against where this branch forked off
   `origin/<TARGET>`. Every degraded run still produces output that looks correct, so silence
   about it is the one failure mode that misleads.
2. Call CloudAEye's `describe_change` MCP tool with:
   - `session_id`: `SESSION.session_id`
   - `intent`: the user's original task request from this coding session, passed verbatim. Do not paraphrase. If `/cloudaeye:review` already set an intent this turn, pass the same string. Write it from your own working context; do not read `.cloudaeye/session.diff` or run `git diff` to compose it — the server already has the diff.
   - `context`: omit unless you have something extra to pass (e.g. `pr_title`). Identity fields are already on the session.
3. Print the `description` field from the response verbatim. It is plain markdown — a `# Change Description` paragraph followed by an `## Important Changes` bullet list — meant for direct consumption (no XML wrappers, no `<details>`). For trivial diffs the description is a single-sentence "Trivial change —" line; do not pad it.

   Call `mcp__plugin_cloudaeye_cloudaeye__describe_change`; it is Claude Code asks before its first use.

   Check `context_refresh.status` first. On `skipped` or `failed` the stored code graph was not refreshed with this diff, so the answer is based on the pre-edit code plus the diff text alone — say so in one line and quote `context_refresh.reason`. It is usually an expired GitHub installation token, which the user has to fix server-side.

## Notes

- This is a **single-enqueue** skill: submit once, poll the job, print the
  original description, done. No resubmission or fix-and-retry loop.
- Good moments to invoke: before opening a PR, before writing a commit message, when the user asks "what did I just change?"
- Pre-commit only: the diff is always `git diff` (working tree vs `HEAD`). Committing moves `HEAD`; the review session persists.
- Without a `client_git_token` / `client_git_owner` configured on the server, the code-context refresh is skipped and the description falls back to diff-only analysis (still works, just less precise on blast radius).
- If `describe_change` is unavailable (MCP not connected), warn the user and skip — do not attempt to describe the diff yourself from `git diff` output.
- The full investigation trace is logged on the server under `query_logs/` keyed by `run_id` (included in the response's `eval_summary`).
