---
name: check-task
description: Check whether the uncommitted changes in this repo actually do what the task asked. Takes a GitHub issue URL, Jira ticket IDs, a mixed reference list, or freeform task text, and returns a DONE / NOT DONE verdict with a per-requirement checklist and the gaps.
when_to_use: Use before marking work complete, or when the user asks whether the change satisfies an issue, a ticket, or the request they made. Accepts an issue URL, IDs like PROJ-123, a list of both, or plain text.
argument-hint: "[issue URL | TICKET-123 | task description]"
allowed-tools: ["Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__start_session", "mcp__cloudaeye__start_session", "mcp__plugin_cloudaeye_cloudaeye__check_task", "mcp__cloudaeye__check_task", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
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

   Run exactly this one command, alone in its Bash call (that is what lets it run without asking the user for permission):

   ```bash
   sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae start
   ```

   Its first line is JSON. Call `mcp__plugin_cloudaeye_cloudaeye__start_session` with every field of that line, unchanged, and keep the answer as `SESSION`; its `session_id` is the one every later call takes.

   - `SESSION.gate` is `repository`: the repository is not connected to CloudAEye yet. Run `sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide connect-repository` and follow it.
   - The tool is unavailable, or `status` is `error`: stop and tell the user to authenticate CloudAEye through `/mcp`.
   - `SESSION.upload_needed` is `false`: the server already has this exact change. Skip the upload.
   - Otherwise upload the change: exactly this one command, alone in its Bash call, with `SESSION` as JSON inside single quotes. The script checks the values itself and never prints a token.

     ```bash
     sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae upload '<SESSION as JSON>'
     ```

   Read the summary lines — the upload's when it ran, the first command's when it was skipped — and don't re-derive them:

   | output | what to do with it |
   |---|---|
   | `cloudaeye_error=…` | Stop and report it. Never print `upload_token` or `key_token`. |
   | `diff_bytes=0` | Nothing pending — report "nothing to check — no pending changes" and stop. |
   | `prior_task` | Offer it for reuse in step 2; never reuse it silently. |
   | `base_source=fork_point` | The right baseline: the fork point off the integrated branch, not its tip. Name the branch and `base_age`; a very old baseline may miss newer merged work. |
   | `base_source=head` | Degraded: only working-tree edits are in the diff. Say so. If `SESSION` carries `setup_required`, report its `reason` and `remedy` as written; never quote `target_branch_error`, which names an internal record. |
   | `upload_http=` not `200` | The diff never reached the server. Stop; otherwise a stale result can look clean. |

   **Which baseline applied must reach the user.** Every degradation still produces output that looks correct, so silence about it is the one failure mode that misleads.
2. Establish the task to verify against. This is the one input the user must supply:
   - **If an invocation argument was given** (see Arguments above), use it — skip the prompt.
   - **Else if step 1 printed a non-empty `prior_task`** (a `check_task` ran against this review session before, no commit since), offer to reuse it: show `prior_task.task_description` (truncated) and ask "verify against this same task again, or a new one?" Don't silently reuse — confirm first.
   - **Otherwise ask the user** for one of:
     - a **GitHub issue URL** (`https://github.com/<owner>/<repo>/issues/<n>`) → set `task_source="github-issue"` and pass the URL verbatim as `task_description`. The server re-fetches title + body + comments whenever the check runs, so new collaborator comments flow through automatically — never paste the issue body yourself when a URL is available.
     - **Jira ticket IDs** (`[PROJ-123, PROJ-124]`) → set `task_source="jira"` and pass the comma-separated keys (brackets stripped, e.g. `PROJ-123, PROJ-124`) as `task_description`. Each ticket is fetched server-side (summary + description, re-pulled whenever the check runs).
     - **freeform task text** (a spec excerpt or plain description) → pass it verbatim as `task_description` and set `task_source` to `spec` or `user-text`.
   - Do not summarise or paraphrase the task. The server extracts requirements from the exact text.
3. Write a one-paragraph `intent` describing **the code change you just made in this round of edits** — used by the verifier as a focus signal (it still verifies every claim against the actual diff).
   - **Do not read the diff to write this.** No `cat .cloudaeye/session/session.diff`, no `git diff`. You made these edits — the intent comes from your own working context. The diff is already uploaded and the server is what analyses it, so reading it back spends the developer's context window re-deriving what you already know, on a file that can run to thousands of lines. If you genuinely did not make the changes (a resumed session, or the user edited by hand), say so inside the intent itself, never as a line to the user, and use `git diff --stat` for the file list — never the full diff.
   - **First check on a review session:** describe what you implemented and why.
   - **Re-check after the user asked you to close gaps:** reference the prior gaps by number and explain how each was addressed, or why it was intentionally left. Don't restate the original task — the verifier already has it via `task_description`.
4. Call CloudAEye's `check_task` MCP tool with:
   - `session_id`: `SESSION.session_id`
   - `task_description`: the URL (github-issue) or verbatim task text from step 2
   - `task_source`: `github-issue` / `jira` / `spec` / `user-text` (defaults to `user-supplied` if omitted)
   - `intent`: the summary from step 3
   - `context`: optional — only for `pr_title` / `pr_description`. Identity fields are already on the review session.

   Call `mcp__plugin_cloudaeye_cloudaeye__check_task`; it is pre-approved in this skill's frontmatter.

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
