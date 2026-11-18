---
name: describe
description: Describe the uncommitted changes in this repo — a Change Description heading and an Important Changes bullet list, in plain markdown ready to paste into a PR or a commit message. Trivial diffs short-circuit to one line.
when_to_use: Use when the user asks what changed, for a PR description, a commit message, or a summary of the pending diff.
allowed-tools: ["Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__start_session", "mcp__cloudaeye__start_session", "mcp__plugin_cloudaeye_cloudaeye__describe_change", "mcp__cloudaeye__describe_change", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
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
   | `diff_bytes=0` | Nothing pending — report "nothing to describe" and stop. |
   | `base_source=fork_point` | The right baseline: the fork point off the integrated branch, not its tip. Name the branch and `base_age`; a very old baseline may miss newer merged work. |
   | `base_source=head` | Degraded: only working-tree edits are in the diff. Say so. If `SESSION` carries `setup_required`, report its `reason` and `remedy` as written; never quote `target_branch_error`, which names an internal record. |
   | `upload_http=` not `200` | The diff never reached the server. Stop; otherwise a stale result can look clean. |

   **Which baseline applied must reach the user.** Every degradation still produces output that looks correct, so silence about it is the one failure mode that misleads.
2. Call CloudAEye's `describe_change` MCP tool with:
   - `session_id`: `SESSION.session_id`
   - `intent`: the user's original task request from this coding session, passed verbatim. Do not paraphrase. If `/cloudaeye:review` already set an intent this turn, pass the same string. Write it from your own working context; do not read `.cloudaeye/session/session.diff` or run `git diff` to compose it — the server already has the diff.
   - `context`: omit unless you have something extra to pass (e.g. `pr_title`). Identity fields are already on the session.
3. Print the `description` field from the response verbatim. It is plain markdown — a `# Change Description` paragraph followed by an `## Important Changes` bullet list — meant for direct consumption (no XML wrappers, no `<details>`). For trivial diffs the description is a single-sentence "Trivial change —" line; do not pad it.

   Call `mcp__plugin_cloudaeye_cloudaeye__describe_change`; it is pre-approved in this skill's frontmatter.

   Check `context_refresh.status` first. On `skipped` or `failed` the stored code graph was not refreshed with this diff, so the answer is based on the pre-edit code plus the diff text alone — say so in one line and quote `context_refresh.reason`. It is usually an expired GitHub installation token, which the user has to fix server-side.

## Notes

- This is a **single-enqueue** skill: submit once, poll the job, print the
  original description, done. No resubmission or fix-and-retry loop.
- Good moments to invoke: before opening a PR, before writing a commit message, when the user asks "what did I just change?"
- Pre-commit only: the diff is always `git diff` (working tree vs `HEAD`). Committing moves `HEAD`; the review session persists.
- Without a `client_git_token` / `client_git_owner` configured on the server, the code-context refresh is skipped and the description falls back to diff-only analysis (still works, just less precise on blast radius).
- If `describe_change` is unavailable (MCP not connected), warn the user and skip — do not attempt to describe the diff yourself from `git diff` output.
- The full investigation trace is logged on the server under `query_logs/` keyed by `run_id` (included in the response's `eval_summary`).
