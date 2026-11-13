---
name: inspect
description: Bug-hunting CloudAEye pass over the uncommitted changes in this repo, over one file or directory of them, or over an open pull request given its number — logic errors, edge cases, input validation, error handling, concurrency, dead imports. Security is left to its own pass, so this is the cheap one to run after finishing a coding task. Reports findings; it never edits code on its own.
when_to_use: Use after completing a coding task and before reporting done, or when the user asks you to check or review what you just changed. Security categories are opt-in — use /cloudaeye:security or /cloudaeye:review for those.
argument-hint: "[path | #PR] [--critical] [--model MODEL] [--model-provider PROVIDER] [--invert-model true|false]"
allowed-tools: ["Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__start_session", "mcp__cloudaeye__start_session", "mcp__plugin_cloudaeye_cloudaeye__inspect_diff", "mcp__cloudaeye__inspect_diff", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
---

## Queued Result

Submit the analysis once. An answer without `job_id` is the response itself
(report `status: error` and stop). With a `job_id`, call
`mcp__plugin_cloudaeye_cloudaeye__get_job_result(job_id, wait_seconds=110, since=<last progress_id>, report="review")`
again and again, with no pause, while `status` is `queued`, `running` or
`retrying`. The server keeps each call open while the job runs.

- Right before submitting, print:
  `⏳ CloudAEye is checking your change for bugs. This can take a few minutes; progress shows below.`
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

## What the user typed

| Argument | What to do |
|---|---|
| *none* | The working tree: every uncommitted change. Go straight to **Steps**. |
| `#405`, or bare digits like `405` | A pull request. First run `sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide pull-request-run`, and follow it where it differs from the steps. |
| a path: `src/auth/login.ts`, `src/auth/` | Only the changes under it. First run `sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide scoped-run`. |
| `--critical` `--high` `--medium` `--low`, `--model`, `--model-provider`, `--invert-model` | First run `sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide review-flags`. These combine with any row above. |

Digits mean a pull request; a directory named `405` is written `./405`. Each guide is that one
command, alone in its Bash call; run the ones the arguments call for before step 1.

## Steps

1. Set up the session.

   Run exactly this one command, alone in its Bash call (that is what lets it run without asking the user for permission):

   ```bash
   sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae start --review --guide review-settings
   ```

   Its first line is JSON. Call `mcp__plugin_cloudaeye_cloudaeye__start_session` with every field of that line, unchanged, and keep the answer as `SESSION`; its `session_id` is the one every later call takes.

   - `SESSION.gate` is `repository`: the repository is not connected to CloudAEye yet. Run `sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide connect-repository` and follow it.
   - The tool is unavailable, or `status` is `error`: stop and tell the user to authenticate CloudAEye through `/mcp`.
   - `SESSION.upload_needed` is `false`: the server already has this exact change. Skip the upload.
   - Otherwise upload the change: exactly this one command, alone in its Bash call, with `SESSION` as JSON inside single quotes. The script checks the values itself and never prints a token.

     ```bash
     sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae upload '<SESSION as JSON>' --review --guide review-settings
     ```

   Read the summary lines — the upload's when it ran, the first command's when it was skipped — and don't re-derive them:

   | output | what to do with it |
   |---|---|
   | `cloudaeye_error=…` | Stop and report it. Never print `upload_token` or `key_token`. |
   | `diff_bytes=0` | Nothing pending — report "nothing to review" and stop. |
   | `settings:` | The team's settings as JSON (`SETTINGS`). When any apply to this change, `settings-guide:` follows them and says what to pass; with none, nothing follows and nothing changes. |
   | `base_source=fork_point` | The right baseline: the fork point off the integrated branch, not its tip. Name the branch and `base_age`; a very old baseline may miss newer merged work. |
   | `base_source=head` | Degraded: only working-tree edits are in the diff. Say so. If `SESSION` carries `setup_required`, report its `reason` and `remedy` as written; never quote `target_branch_error`, which names an internal record. |
   | `upload_http=` not `200` | The diff never reached the server. Stop; otherwise a stale result can look clean. |

   **Which baseline applied must reach the user.** Every degradation still produces output that looks correct, so silence about it is the one failure mode that misleads.

2. Write a one-paragraph intent summary.

   **The same change as last time** (`SESSION.upload_needed` is `false`, or the upload printed `diff_unchanged=true`): **write no intent and pass none.** The session keeps the one this change was reviewed with, so the server answers from what it stored, in seconds and at no cost; a new paragraph, however close, reads as a new instruction and runs the whole review again. The one exception: the user asked you to leave a flagged finding alone, or to look at something else this time — then write a new intent that says so.

   **Otherwise** describe **the code change you just made in this round of edits** — not the broader task, not a re-statement of the original ask. The planner uses this verbatim to decide what to focus on. Intent is also the **only** mechanism for telling the inspector to leave a previously-flagged issue alone — there's no separate suppression channel. Be specific so the user can see, in your visible intent, what you're asking the inspector to skip.
   - **Do not read the diff to write this.** No `cat .cloudaeye/session/session.diff`, no `git diff`. You made these edits — the intent comes from your own working context, and the server is what analyses the diff. If you genuinely did not make the changes (a resumed session, or the user edited by hand), say so inside the intent itself, never as a line to the user, and take the file list from the `changed_files=` line — never run a git command for it, and never read the diff.
   - **First inspect on a review session:** describe what you implemented and why.
   - **Re-inspect after the user asked you to fix something:** say which prior findings you addressed and how, plus any you intentionally left and why. Reference the prior finding's tag so the planner can map it back. Example: "Fixed `tests/test_transformers.py/issue-1` by adding `assert` around `np.array_equal`. Left `sklearn_pandas/transformers.py/issue-2` alone because the user said pandas metadata loss is acceptable for this transformer." Don't repeat the original task — the planner already saw it.
   - **Trade-offs and surprises** worth flagging belong here too (e.g. "switched serialization to pickle instead of joblib because of a Windows path issue").
3. Call CloudAEye's `inspect_diff` MCP tool (`mcp__plugin_cloudaeye_cloudaeye__inspect_diff`, pre-approved in this skill's frontmatter) with:
   - `session_id`: `SESSION.session_id`
   - `intent`: the summary from step 2; left out altogether for the same change as last time
   - `profile`: `"inspect"` — **always this value from this skill.** It runs the bug categories only. Do not pass `"security"` or `"review"` here; those belong to `/cloudaeye:security` and `/cloudaeye:review`, which the user invokes deliberately.
   - whatever a guide you ran, or the `settings-guide:`, told you to pass: `min_severity`, `review_model`, `model_provider`, `invert_model`, `rules`, `llm_key`, `context.scope_path`. Pass none of them otherwise; never default to a floor or a model nobody asked for.
   - `context`: otherwise only `pr_title` / `pr_description`. Do not pass `review_config` or `report_types`; either one overrides the profile.

   You do **not** need to read the changed source files yourself before calling — the server has the post-edit contents staged and examines them with its own tooling.
4. Report the response to the user:
   - **First: `verdict` is `error`, or the response carries a `degraded` block.** The review ran with no post-edit source staged, so every prompt saw an empty file and the secret scan never picked a detector (`secret_scan.detector: "none"` is the tell). **Report it as a failed run and stop — do not present the findings, and never call it clean.** `degraded.cause` names the upstream reason when there is one; `context_refresh.status` of `skipped`/`failed` carries it verbatim, and an expired GitHub installation token is the usual culprit. The server does not cache a degraded run, so re-running once the cause is fixed gives a real review.
   - The `verdict` (`approve` / `request_changes`).
   - **Report what came back, not what didn't.** Don't list report types that produced no findings, don't quote timings, file counts or detector names that worked, and don't explain which prompts didn't fire. A diagnostic field the response *does* carry is there because it changes what the result means — those you report.
   - The full list of `findings` (file, line, severity, message).
   - **Print each finding with its `n`, exactly as the server numbered it** — `1.`, `2.`, `3.` — and never renumber. That number is what the user types back at `/cloudaeye:implement [1,3]`, and the server resolves it against its own stored report, so a list you renumbered would aim the fix at the wrong finding.
   - If there are findings, ask which (if any) to fix, and say they can answer with the numbers — "1 and 3", or `/cloudaeye:implement [1,3]` for a plan grounded in the code graph. Do not start editing until the user replies. After fixing, re-invoke `/cloudaeye:inspect`; the server resumes the same review session.

## Notes

- Submit analysis once, resolve its response using **Queued Result**, report the output, then stop. No fix-and-retry loop inside the skill.
- **Bugs only.** This profile runs: logic errors, syntax/compile breaks, edge cases, input validation, concurrency safety, error handling, code clarity, naming consistency, and code signatures. Code signatures include a **compiler type check** over the AST graph, which catches callers broken by a changed definition even when those callers are in files this diff never touched — so a `code_signature` finding may point at a file you didn't edit. That's the point; don't dismiss it as out of scope. Security prompts are **not** part of it — they cost real tokens on every scanned file, so they are routed behind `/cloudaeye:security` (security surface only) and `/cloudaeye:review` (bugs + security). If the change touches authentication, input handling from untrusted sources, deserialization, secrets, crypto, LLM prompts, tool definitions, or agent orchestration, say so and suggest `/cloudaeye:security` — don't silently skip it, and don't run it uninvited.
- **Re-inspection is user-driven.** The user may say "fix issue X and run inspect again" — just re-invoke this skill. The server resumes the same review session for the OAuth account and repository; your job on re-invocation is a sharp intent (step 2) that describes only the most recent change.
- Pre-commit only: the diff is `git diff` against the fork point. Committing moves `HEAD`, but the review session persists — its recorded `head` is refreshed on the next call, and prior intent and task context carry across.
- If `inspect_diff` is unavailable (MCP not connected), warn the user and skip.
