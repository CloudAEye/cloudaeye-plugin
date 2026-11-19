---
name: check-task
description: Check whether the uncommitted changes in this repo actually do what the task asked. Takes a GitHub issue URL, Jira ticket IDs, a mixed reference list, or freeform task text, and returns a DONE / NOT DONE verdict with a per-requirement checklist and the gaps.
when_to_use: Use before marking work complete, or when the user asks whether the change satisfies an issue, a ticket, or the request they made. Accepts an issue URL, IDs like PROJ-123, a list of both, or plain text.
argument-hint: "[issue URL | TICKET-123 | task description]"
allowed-tools: Read, Grep, Glob, LS
---

## Queued Result

Submit the analysis once. An answer without `job_id` is the response itself
(report `status: error` and stop). With a `job_id`, call
`mcp__plugin_cloudaeye_cloudaeye__get_job_result(job_id, wait_seconds=110, since=<last progress_id>)`
again and again, with no pause, while `status` is `queued`, `running` or
`retrying`. The server keeps each call open while the job runs.

- Right before submitting, print:
  `⏳ CloudAEye is checking your change against the task. This can take a few minutes; progress shows below.`
- Print `⏳ ` + `message` only when `progress_id` changed, exactly as given: no
  job ids, no "polling", no commentary, never a line the server did not send.
- On `completed`, print `✅ CloudAEye finished.` and use its `result` as **the response** below, keeping the
  tool's fields. An inner `status: error` is a refusal, not a clean result.
- If the answer carries `next_run`, end with the heading
  `**To get more from the next run**` and each entry as a bullet, exactly as given.
- Stop after 150 calls or 30 minutes and say the job is still running, with its
  id. On `failed` or `error`, report it and stop. Never submit again to check
  progress, and finish the job before any edit, upload or other command on the
  same session.

## Arguments

The skill accepts an optional task spec as its invocation argument. When present, use it as the task input and **do not re-prompt** the user (still confirm before reusing a `prior_task`). Recognised forms:

- **Jira ticket IDs** — a bracketed or bare comma list of `PROJECT-NUMBER` keys, e.g. `/cloudaeye:check-task [PROJ-123, PROJ-124]` or `/cloudaeye:check-task PROJ-123`. Detect with `\b[A-Z][A-Z0-9]+-\d+\b`. Route to `task_source="jira"`.
- **GitHub issue URL** — `https://github.com/<owner>/<repo>/issues/<n>`. Route to `task_source="github-issue"`. Short refs (`#42`, `owner/repo#42`) and mixed Jira+GitHub lists (`[PROJ-123, #42]`) also resolve server-side.
- **Freeform text** — anything else. Route to `task_source="user-text"` (or `jira`/`spec` if the text is clearly that). Text that merely *mentions* tickets ("verify PROJ-123 is handled, keep retries intact") is fine as-is — a server-side triage model extracts the references and keeps the extra requirements; don't restructure it.

With no argument, fall back to asking the user (step 2).

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
   empty, or the command stops at a `git` error before the upload runs, read `${CLAUDE_PLUGIN_ROOT}/resources/skills/no-target-branch.md`
   instead.

   ```bash
   git -c credential.helper= fetch -q origin '<TARGET>' 2>/dev/null; mkdir -p .cloudaeye && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Upload-Token:%s"\n' '<UPLOAD_URL>' '<UPLOAD_TOKEN>' | tee .cloudaeye/upload.curl && git rev-parse --git-path index | xargs -I{} cp -p {} .cloudaeye/index && export GIT_INDEX_FILE=.cloudaeye/index && git add -N . && git diff --merge-base 'origin/<TARGET>' --output=.cloudaeye/session.diff -- . && git merge-base HEAD 'origin/<TARGET>' | curl -sS --fail-with-body -K .cloudaeye/upload.curl -F 'base_sha=<-' -F 'file=@.cloudaeye/session.diff'
   ```

   It prints the upload's settings file, then the server's answer as JSON. Never print the upload token.
   An upload error (`(22)` and a message): the diff never reached the server. Stop; otherwise a stale result can look clean.

   | what came back | what to do with it |
   |---|---|
   | `diff_files` is `0` | Nothing pending — report "nothing to check — no pending changes" and stop. |
   | `changed_files` | The changed paths (up to 20, `more_files` beyond). Take a file list from here, never from a git command of your own. |

   **Say which baseline applied**, in one short line and nothing more, with no code
   formatting: *Baseline: <TARGET> at its fork point.* Every degraded run still produces output that looks correct, so silence
   about it is the one failure mode that misleads.
2. Establish the task to verify against. This is the one input the user must supply:
   - **If an invocation argument was given** (see Arguments above), use it — skip the prompt.
   - **Else if step 1 printed a non-empty `prior_task`** (a `check_task` ran against this review session before, no commit since), offer to reuse it: show `prior_task.task_description` (truncated) and ask "verify against this same task again, or a new one?" Don't silently reuse — confirm first.
   - **Otherwise ask the user** for one of:
     - a **GitHub issue URL** (`https://github.com/<owner>/<repo>/issues/<n>`) → set `task_source="github-issue"` and pass the URL verbatim as `task_description`. The server re-fetches title + body + comments whenever the check runs, so new collaborator comments flow through automatically — never paste the issue body yourself when a URL is available.
     - **Jira ticket IDs** (`[PROJ-123, PROJ-124]`) → set `task_source="jira"` and pass the comma-separated keys (brackets stripped, e.g. `PROJ-123, PROJ-124`) as `task_description`. Each ticket is fetched server-side (summary + description, re-pulled whenever the check runs).
     - **freeform task text** (a spec excerpt or plain description) → pass it verbatim as `task_description` and set `task_source` to `spec` or `user-text`.
   - Do not summarise or paraphrase the task. The server extracts requirements from the exact text.
3. Write a one-paragraph `intent` describing **the code change you just made in this round of edits** — used by the verifier as a focus signal (it still verifies every claim against the actual diff).
   - **Do not read the diff to write this.** No `cat .cloudaeye/session.diff`, no `git diff`. You made these edits — the intent comes from your own working context. The diff is already uploaded and the server is what analyses it, so reading it back spends the developer's context window re-deriving what you already know, on a file that can run to thousands of lines. If you genuinely did not make the changes (a resumed session, or the user edited by hand), say so inside the intent itself and never to the user: your reply says nothing about the intent (not what it says, not that you wrote one, not who made the change), and use `git diff --stat` for the file list — never the full diff.
   - **First check on a review session:** describe what you implemented and why.
   - **Re-check after the user asked you to close gaps:** reference the prior gaps by number and explain how each was addressed, or why it was intentionally left. Don't restate the original task — the verifier already has it via `task_description`.
4. Call CloudAEye's `check_task` MCP tool with:
   - `session_id`: `SESSION.session_id`
   - `task_description`: the URL (github-issue) or verbatim task text from step 2
   - `task_source`: `github-issue` / `jira` / `spec` / `user-text` (defaults to `user-supplied` if omitted)
   - `intent`: the summary from step 3
   - `context`: optional — only for `pr_title` / `pr_description`. Identity fields are already on the review session.

   Call `mcp__plugin_cloudaeye_cloudaeye__check_task`; it is Claude Code asks before its first use.

   You do **not** need to read the changed source files yourself before calling — the server has the post-edit file contents staged and examines them via its own tooling.
5. Print the `report` field from the response verbatim. It is rendered markdown — a `# Task Completion Check` heading, a status line, a progress bar over met requirements, a per-requirement table (✅ done / ⚠️ partial / ❌ not done), gaps, and any out-of-scope changes. Don't re-summarise or re-format it; the counts and the bar are computed server-side and re-typing them is how they drift.

   Check `context_refresh.status` first. On `skipped` or `failed` the stored code graph was not refreshed with this diff, so the answer is based on the pre-edit code plus the diff text alone — say so in one line and quote `context_refresh.reason`. It is usually an expired GitHub installation token, which the user has to fix server-side.

   The response also carries a machine-readable `verdict`: **`DONE`** (every requirement met), **`NOT_DONE`** (anything less — a single partial requirement is not "done"), or **`ERROR`** (the check could not run; not a judgement on the change). On `NOT_DONE`, ask the user whether they'd like you to close the listed gaps. Don't start editing until the user replies; if they say yes, make the edits and re-invoke `/cloudaeye:check-task` (the server resumes the same review session and offers the prior task for reuse). On `ERROR`, say what failed and offer the workaround — usually pasting the ticket body as freeform text.

## Notes

- Submit analysis once, resolve its response using **Queued Result**, print the output, then stop. No fix-and-retry loop inside the skill.
- **The task is persisted on the review session.** After a successful check, a later `start_session` resume surfaces it as `prior_task` so the user isn't re-prompted. For `github-issue` the stored value is the URL (re-fetched whenever the check runs), not a frozen snapshot — so a re-check picks up new issue comments.
- **The same change against the same task is answered from the stored check** (`cached: true`): nothing runs and nothing is billed. Say it was reused. A code change, a different task or a new intent runs it again and re-reads the ticket — so after the ticket itself was edited on an unchanged change, re-check with the new text or a fresh intent.
- **GitHub fetch requires `client_git_token` on the server.** If it's missing, or the URL is malformed / the token lacks access, `check_task` returns a structured `error` (not a verdict) — surface it and offer to let the user paste the issue body as freeform `user-text` instead.
- **Jira fetch goes through the tenant's CloudAEye Jira (Forge) app — same integration as cloud reviews.** The tenant comes from the verified OAuth token used by `start_session`, never from repository or machine config. The server side needs `BITBUCKET_FUNCTION_KEY` and the Mongo store (`TEST_RCA_MONGODB_URL`), and the tenant must have the CloudAEye Jira app installed. When they're missing or a key doesn't resolve: a task that is *only* ticket refs returns a structured `error` (nothing to judge — surface it and offer pasting the ticket body as `user-text`); a task that also carries prose proceeds against the prose with a visible "reference(s) not checked" note in the report. A partially-resolved list likewise carries a note — a verdict never silently implies an unfetched ticket was verified.
- Pre-commit only: the diff is always `git diff` (working tree vs `HEAD`). Committing moves `HEAD`, but the review session persists — its recorded `head` is refreshed on the next call, and the stored task carries across, so `prior_task` still comes back after a commit.
- Without `client_git_token` / `client_git_owner` configured, the code-context refresh is skipped and verification falls back to diff-only analysis (still works, just less precise on end-to-end wiring).
- If `check_task` is unavailable (MCP not connected), warn the user and skip — do not attempt to judge the diff against the task yourself from `git diff` output.
- The full investigation trace is logged on the server under `query_logs/` keyed by `run_id` (included in the response's `eval_summary`).
