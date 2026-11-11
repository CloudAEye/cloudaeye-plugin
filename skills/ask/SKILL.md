---
name: ask
description: Ask a free-form question about the uncommitted changes in this repo and get an answer grounded in the repository's code graph — callers, definitions and usage traces, not just the diff text. Returns an answer, not a review, and never edits code.
when_to_use: Use for blast-radius questions ("what else calls this?"), "what did this do before?", "is this pattern used elsewhere?", or a second opinion the coding agent cannot give from its own context window.
argument-hint: "[question about the pending change]"
allowed-tools: ["Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__start_session", "mcp__cloudaeye__start_session", "mcp__plugin_cloudaeye_cloudaeye__ask", "mcp__cloudaeye__ask", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
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

## When to run

The user invoked `/cloudaeye:ask`, or asked a question about the pending change that you cannot answer confidently from what you have already read. That second case is the important one: the server has the whole repository's AST graph indexed, and you have a context window. Questions worth handing over:

- **Blast radius** — "what else calls this?", "who depends on this interface?"
- **Prior behaviour** — "what did this function do before my change?"
- **Repo-wide patterns** — "is this error handled the same way elsewhere?", "do other callers already do this check?"
- **Second opinion on a specific line** — "is this lock actually protecting anything?"

Do **not** use it as a review. It returns no findings and no verdict. If the user wants problems found, that's `/cloudaeye:inspect` (bugs), `/cloudaeye:security` (security), or `/cloudaeye:review` (both).

## Steps

### Repository initialization gate

Run this first: exactly the one command shown, alone in its Bash call (that is
what lets it run without asking the user for permission).

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae preflight
```

It prints `provider`, `repo_url`, `branch` and `head`. Call
`mcp__plugin_cloudaeye_cloudaeye__initialize_repository` with `provider`,
`repo_url` and an empty `monitor_branch`, and keep its response as `INIT`.

- `ready` or `initialized`: `INIT.repo_full` is the authoritative `repo` from
  here on; do not recompute it from local Git.
- Anything else (`branch_required`, `setup_required`, an error): read
  `${CLAUDE_PLUGIN_ROOT}/resources/skills/connect-repository.md` and follow it.

Any `cloudaeye_error=…` line from a command: report it and stop.

Do not go on until this gate reports `ready` or `initialized`.


1. Prepare and upload the review session.

   The initialization gate already printed the current `branch` and `head`.

   Call `mcp__plugin_cloudaeye_cloudaeye__start_session` with `INIT.repo_full`, the
   current `branch`, and `head` — no `language`; the server derives the
   tech-stack hint from the uploaded diff. If the tool is unavailable or returns
   `status: error`, stop and tell the user to authenticate CloudAEye through `/mcp`.

   Upload the change: exactly this one command, alone in its Bash call, with `start_session`'s whole answer as JSON inside single quotes. The script checks the values itself and never prints a token.

   ```bash
   sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae upload '<the start_session answer as JSON>'
   ```

   Read the two summary lines and the `start_session` result; don't re-derive them:

   | output | what to do with it |
   |---|---|
   | `start_session` unavailable or `status: error` | Stop and tell the user to authenticate CloudAEye through `/mcp`. |
   | `cloudaeye_error=…` | Stop and report it. Never print `upload_token`. |
   | `session_id=…` | Pass it to the MCP tool. |
   | `diff_bytes=0` | No pending changes. **Do not stop** — unlike the review skills, a question about the existing code is still answerable. |
   | `base_source=fork_point` | Correct baseline: the fork point off the integrated branch, not its tip. Name the branch and `base_age`; a very old baseline may miss newer merged work. |
   | `base_source=head` | Degraded: only working-tree edits are in the diff. Say so. If `start_session` returned `setup_required`, report its `reason` and `remedy` verbatim — that is the actionable form. Do **not** quote `target_branch_error`: it names an internal record ("no datastore credentials for tenant 99") and tells the user nothing they can act on. |
   | `upload_http=` not `200` | The diff never reached the server. Stop; otherwise a stale result can look correct. |

   **Which baseline applied must reach the user.** Every degradation still produces output that looks correct, so silence about it is the one failure mode that misleads. Keeping the clone current is the developer's job — the skill never forces a fetch, it just refuses to hide what it used.
2. Call CloudAEye's `ask` MCP tool with:
   - `session_id`: the `session_id` printed by step 1
   - `question`: the user's question **verbatim**. Do not summarise it, do not expand it into a "better" question, do not split it into several. The phrasing is what they meant; a rewritten question gets a different answer to a question nobody asked. If the question was implicit in conversation ("wait, does that break the retry path?"), quote it as they said it.
   - `intent`: optional — one paragraph on what you just changed, if the question is about your edit. Context for the question, not its subject. Write it from your own working context; do not read `.cloudaeye/session/session.diff` or run `git diff` to compose it — the server already has the diff.
   - `context`: optional — only `pr_title` / `pr_description`.

   Call `mcp__plugin_cloudaeye_cloudaeye__ask`; it is pre-approved in this skill's frontmatter.

   You do **not** need to read the changed source files yourself first — the server has the post-edit contents staged and its own tooling to trace through them.
3. Report the response:
   - Print the `answer` field as-is. It is plain markdown written to be read directly.

   Check `context_refresh.status` first. On `skipped` or `failed` the stored code graph was not refreshed with this diff, so the answer is based on the pre-edit code plus the diff text alone — say so in one line and quote `context_refresh.reason`. It is usually an expired GitHub installation token, which the user has to fix server-side.
   - If the answer names files you have not read and the user's next step depends on them, offer to open them — don't silently re-derive the answer yourself.
   - `files_visited` shows what the answer is grounded in. Surface it when the answer is surprising or the user pushes back, so they can see the basis rather than take it on trust.

## Notes

- **Single-shot** — one question, one answer. If the user has a follow-up, invoke the skill again with the follow-up as the new question; the server resumes the same session.
- **The answer can be wrong.** It is a model reasoning over a code graph, not a compiler. When it contradicts something you have directly read in the source, say so rather than deferring to it — and prefer the file you read.
- **It answers; it does not review.** If the answer volunteers problems, that's a bonus, not the contract. Findings come from the review skills.
- Pre-commit: the diff is `git diff` (working tree vs `HEAD`). Committing moves `HEAD`; the session persists and its recorded `head` is refreshed on the next call.
- If `ask` is unavailable (MCP not connected), warn the user and answer from your own context instead, saying that's what you did.
