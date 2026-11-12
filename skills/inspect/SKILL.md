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

## Three modes

Parse the model options and severity flags below first. Decide the mode only from the remaining path or PR argument:

| Argument | Mode |
|---|---|
| *none* | **Working tree** — every uncommitted change. This is the usual one. |
| `#405`, or bare digits like `405` | **Pull request** — PR 405 of this repository. |
| anything else — `src/auth/login.ts`, `src/auth/`, `src/auth` | **Path** — only the changes under that file or directory. |
| `--critical` `--high` `--medium` `--low` | Combine with any mode above — reports that level **and higher**. |

Digits mean a pull request. If the user really means a directory named `405`, they write `./405` and you treat it as a path.

### Model options

These options apply only to this invocation; they never change saved settings.

| Flag | `inspect_diff` argument | Value |
|---|---|---|
| `--model` | `review_model` | Model family (for example, `gpt`) or exact model ID. |
| `--model-provider` | `model_provider` | Hosting provider (for example, `azure`). |
| `--invert-model` | `invert_model` | Boolean `true` or `false`, never a string. |

An option the user did not supply comes from the repository's LLM settings when
they set it (see **Your settings**); otherwise omit it. In particular, an omitted
`invert_model` uses the tenant's saved inversion setting, not a client-side default. When
inversion is enabled, this Claude Code flow uses the configured GPT reviewer.
An explicit model or provider takes precedence over inversion. Pass all supplied
options to the server; it resolves supported models, providers, and credentials.
Reject missing values, unknown flags, or an inversion value other than `true`
or `false` before initializing a session. Report server selection errors and
stop; do not retry with a different model or silently drop an option.

```text
/cloudaeye:inspect --invert-model false
/cloudaeye:inspect src/auth/ --high --model gpt
/cloudaeye:inspect --model-provider azure
```

### Path mode

The scope is applied where the diff is made — `git diff <base> -- <path>` — so only that subtree is ever uploaded. A directory covers everything beneath it; a file covers just that file.

**Say what was excluded.** The scoped diff is a subset, so `approve` here means "approve for that path" and reads exactly like "approve". Always name the scope and how many of the changed files it left out — "reviewed 2 of 7 changed files (src/auth/)". The response echoes a `scope` field for the same reason; do not drop it.

**A scoped review is blind outside the scope by construction.** The cross-file checks — the compiler pass that catches callers broken by a changed signature — can only see files in the diff, so a break in a file the path excluded will not be found. Worth one line to the user when the excluded count is not zero.

If the path matches nothing in the diff, say so naming the path and stop. Do not silently widen to the whole change.

### Severity flag

Any mode also takes a floor: `--critical`, `--high`, `--medium`, `--low`.

```
/cloudaeye:inspect --critical
/cloudaeye:inspect src/auth/ --high
/cloudaeye:inspect #405 --critical
```

**It is a floor, not an exact match.** `--high` reports high *and* critical.
Showing a high finding while a critical sat hidden beneath the filter would be
the worst possible reading of the word.

The floor rides into the scan prompt as well as the final filter, so a filtered
review genuinely **costs less** rather than merely showing less — the scan stops
producing candidates the later stages would otherwise pay to verify and format.

Pass it as `min_severity` on the tool call, with the leading dashes stripped.
An unrecognised value is refused by the server; report the error rather than
retrying without the flag, because reviewing everything when the user asked for
critical only is a failure they cannot see.

When a floor was applied the response carries `min_severity`, and `held_back`
counts what sat below it. **Report both.** "No findings" and "no findings at or
above critical, and four below it" are different answers, and only one of them
is true.

### Pull-request mode

Reviews an open pull request of *this* repository. The server fetches the diff from GitHub itself, so there is no upload step and no diff leaves the machine; only the repository identity is read locally.

A pull request must be **open** (drafts are fine), must merge into this repository's **integrated branch** — the one connected to CloudAEye — must **not come from a fork**, and must change **at most 50 files**. The server checks all four before doing any review work and refuses with a reason naming what to do. Report that reason as written and stop — never fall back to reviewing the working tree, which is a different change and would read as an answer to the question the user asked.

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

### Your settings

The team's settings are `.cloudaeye.config` and `.cloudaeye.rules` files in the
repository (`/cloudaeye:config` writes them); one in a directory covers that directory
and below. Step 1 reads the ones that apply to this change's files — from the working
tree before a commit, from the target branch on a pull request — and prints them as
JSON after `settings:`. Keep that JSON as `SETTINGS`; `error` means run without them
(say so in one line). Print each of `problems` once, and on a pull request `pending`
(*this pull request changes <files>; they apply once merged*). Four apply here:

- **`SETTINGS.review.severity_floor`** — the floor when the user gave no severity flag
  (`all` means none). A flag always wins.
- **`SETTINGS.review`'s LLM settings** — each when the user gave no option for it:
  `model` as `review_model`, `provider` as `model_provider` (present only with `llm`
  set to `your own`), `invert_model` as `invert_model`. A flag always wins; say once
  which came from your settings. **An API key** in the settings is sent to CloudAEye by
  step 1 itself: `SETTINGS.review.api_key` says only where it comes from, whether it was
  found and whether it was `sent`. Never read, print or repeat the key, and never pass it
  to a tool.
- **Paths never reviewed** — step 1 leaves them out of the uploaded change, before a
  commit only; on a pull request the server reads the whole pull request.
- **`SETTINGS.rules`** — your team's review rules, passed as `rules` (step 3).

1. Prepare and upload the review session.

   The initialization gate already printed the current `branch` and `head`.

   Call `mcp__plugin_cloudaeye_cloudaeye__start_session` with `INIT.repo_full`, the
   current `branch`, and `head` — no `language`; the server derives the
   tech-stack hint from the uploaded diff. If the tool is unavailable or returns
   `status: error`, stop and tell the user to authenticate CloudAEye through `/mcp`.

   **Pull-request mode:** also pass `pr_number` — the digits the user gave, with any `#` stripped. Then **stop here and go to step 2**: the diff is already on the server, so the whole upload block below is skipped, and running it would compute a working-tree diff nobody asked for.

   On `status: error` in this mode, print the `error` field as written and stop. It is the eligibility refusal — closed pull request, wrong base branch, fork, or over the 50-file limit — and each names a different thing to do. Do not paraphrase it into "the PR could not be reviewed", and do not review the working tree instead.

   On success the response carries a `pull_request` block: number, title, `draft`, `base`, `head`, `head_sha` and `changed_files`. Say which pull request you are reviewing, and say so if it is a draft — the user may have meant a different one, and the head SHA is what makes the review reproducible. Then read your settings as the target branch has them: exactly this one command, alone in its Bash call, with `start_session`'s whole answer as JSON inside single quotes (the script takes the target branch and the changed files from it):

   ```bash
   sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae pr-settings '<the start_session answer as JSON>' --review
   ```

   **Working-tree and path modes only, from here to the end of step 1.** Upload the change: exactly this one command, alone in its Bash call, with `start_session`'s whole answer as JSON inside single quotes. Add `--scope '<the path>'` after the JSON when the user scoped the run to a path. The script checks the values itself and never prints a token.

   ```bash
   sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae upload '<the start_session answer as JSON>' --review
   ```

   Read the two summary lines and the `start_session` result; don't re-derive them:

   | output | what to do with it |
   |---|---|
   | `start_session` unavailable or `status: error` | Stop and tell the user to authenticate CloudAEye through `/mcp`. |
   | `cloudaeye_error=…` | Stop and report it. Never print `upload_token` or `key_token`. |
   | `session_id=…` | Pass it to the MCP tool. |
   | `diff_bytes=0`, `scope=-` | Nothing pending — report "nothing to review" and stop. |
   | `diff_bytes=0` with a scope | Nothing has changed under that path. Say so **naming the path**, and stop. Do not widen to the whole change — they asked about one place. |
   | `diff_files` below `total_files` | A scoped review. Report both — "reviewed 2 of 7 changed files (src/auth/)" — and say the cross-file checks cannot see the excluded ones. `approve` here means approve *for that path*, and nothing else in the output says so. |
   | `skipped_by_settings` above `0` | Your settings left that many changed files out. Say so, naming the patterns; the scope label in step 3 records it. |
   | `settings:` | `SETTINGS` — see **Your settings** above. |
   | `cloudaeye_error=scope_outside_repo` | The path escaped the repository (`..`, absolute, or `~`). Report it and stop. |
   | `base_source=fork_point` | Correct baseline: the fork point off the integrated branch, not its tip. Name the branch and `base_age`; a very old baseline may miss newer merged work. |
   | `base_source=head` | Degraded: only working-tree edits are in the diff. Say so. If `start_session` returned `setup_required`, report its `reason` and `remedy` verbatim — that is the actionable form. Do **not** quote `target_branch_error`: it names an internal record ("no datastore credentials for tenant 99") and tells the user nothing they can act on. |
   | `upload_http=` not `200` | The diff never reached the server. Stop; otherwise a stale result can look clean. |
   | `diff_unchanged=true` | The server already has this exact change — see step 2: pass no `intent`. |

   **Which baseline applied must reach the user.** Every degradation still produces output that looks correct, so silence about it is the one failure mode that misleads. Keeping the clone current is the developer's job — the skill never forces a fetch, it just refuses to hide what it used.
2. Write a one-paragraph intent summary.

   **The same change as last time** (`diff_unchanged=true` on the upload's summary line; in pull-request mode, in `start_session`'s answer): **write no intent and pass none.** The session keeps the one this change was reviewed with, so the server answers from what it stored, in seconds and at no cost; a new paragraph, however close, reads as a new instruction and runs the whole review again. The one exception: the user asked you to leave a flagged finding alone, or to look at something else this time — then write a new intent that says so.

   **Pull-request mode:** you did not write this change, so do not pretend to. Use the pull request's own title and description — the server already put them on the session — and say in one line that the intent is the author's stated purpose rather than yours. Do not open the changed files to invent a better one; the server analyses the diff and reading it back spends the user's context window on work the server is doing anyway.

   **Working-tree and path modes:** describe **the code change you just made in this round of edits** — not the broader task, not a re-statement of the original ask. The planner uses this verbatim to decide what to focus on. Intent is also the **only** mechanism for telling the inspector to leave a previously-flagged issue alone — there's no separate suppression channel. Be specific so the user can see, in your visible intent, what you're asking the inspector to skip.
   - **Do not read the diff to write this.** No `cat .cloudaeye/session/session.diff`, no `git diff`. You made these edits — the intent comes from your own working context. The diff is already uploaded and the server is what analyses it, so reading it back spends the developer's context window re-deriving what you already know, on a file that can run to thousands of lines. If you genuinely did not make the changes (a resumed session, or the user edited by hand), say so inside the intent itself, never as a line to the user, and use `git diff --stat` for the file list — never the full diff.
   - **First inspect on a review session:** describe what you implemented and why.
   - **Re-inspect after the user asked you to fix something:** say which prior findings you addressed and how, plus any you intentionally left and why. Reference the prior finding's tag so the planner can map it back. Example: "Fixed `tests/test_transformers.py/issue-1` by adding `assert` around `np.array_equal`. Left `sklearn_pandas/transformers.py/issue-2` alone because the user said pandas metadata loss is acceptable for this transformer." Don't repeat the original task — the planner already saw it.
   - **Trade-offs and surprises** worth flagging belong here too (e.g. "switched serialization to pickle instead of joblib because of a Windows path issue").
3. Call CloudAEye's `inspect_diff` MCP tool with:
   - `session_id`: the `session_id` printed by step 1
   - `intent`: the summary from step 2; left out altogether for the same change as last time
   - `profile`: `"inspect"` — **always this value from this skill.** It runs the bug categories only. Do not pass `"security"` or `"review"` here; those belong to `/cloudaeye:security` and `/cloudaeye:review`, which the user invokes deliberately.
   - `min_severity`: when the user passed a severity flag, its name with the dashes stripped — `critical`, `high`, `medium` or `low`. Without a flag, `SETTINGS.review.severity_floor` when it is set and not `all`, and say once that the floor came from your settings. Omit it otherwise; never default to a floor nobody asked for.
   - `rules`: `SETTINGS.rules` when there are any — each `{id, text, paths}` as given. `rules_problems` in the answer names any left out; say so.
   - Scope label: when your settings left files out, `context.scope_path` is `"<the path, or the whole change> except <the patterns, comma-separated>"`.
   - `llm_key`: `true` only when `SETTINGS.review.api_key.sent` is `true` and `model_provider` is the settings' provider; omit it otherwise. Never pass the key itself.
   - `review_model`, `model_provider`, `invert_model`: the user's option when supplied, using the mappings in **Model options** above; otherwise the matching LLM setting when set (**Your settings**); omitted otherwise. These are top-level tool arguments, not fields inside `context`.
   - `context`: in **path mode**, set `scope_path` to the path the user gave. It filters nothing — you already narrowed the diff — but it is what makes the response say what it covered, and a narrowed `approve` that does not say so is the one result that misleads. Otherwise only `pr_title`. Identity fields (repo/branch/head/language) are already on the review session, and `review_config` / `report_types` would override the profile.

   Call `mcp__plugin_cloudaeye_cloudaeye__inspect_diff`; it is pre-approved in this skill's frontmatter.

   You do **not** need to read the changed source files yourself before calling — the server already has the post-edit file contents staged and will examine them via its own tooling. Reading them in the agent just burns tokens.
4. Report the response to the user:
   - **First: `verdict` is `error`, or the response carries a `degraded` block.** The review ran with no post-edit source staged, so every prompt saw an empty file and the secret scan never picked a detector (`secret_scan.detector: "none"` is the tell). **Report it as a failed run and stop — do not present the findings, and never call it clean.** `degraded.cause` names the upstream reason when there is one; `context_refresh.status` of `skipped`/`failed` carries it verbatim, and an expired GitHub installation token is the usual culprit. The server does not cache a degraded run, so re-running once the cause is fixed gives a real review.
   - The `verdict` (`approve` / `request_changes`).
   - **Report what came back, not what didn't.** Don't list report types that produced no findings, don't quote timings, file counts or detector names that worked, and don't explain which prompts didn't fire. The response deliberately omits that metadata; narrating its absence turns a three-line result into a wall of caveats. A diagnostic field the response *does* carry is there precisely because it changes what the result means — those you report.
   - The full list of `findings` (file, line, severity, message).
   - **Print each finding with its `n`, exactly as the server numbered it** — `1.`, `2.`, `3.` — and never renumber. That number is what the user types back at `/cloudaeye:implement [1,3]`, and the server resolves it against its own stored report, so a list you renumbered would aim the fix at the wrong finding. The numbers already run 1..N in the order you are told to present them, so grouping and numbering do not fight.
   - If there are findings, ask which (if any) to fix, and say they can answer with the numbers — "1 and 3", or `/cloudaeye:implement [1,3]` for a plan grounded in the code graph. Do not start editing until the user replies. After fixing, re-invoke `/cloudaeye:inspect`; the server resumes the same review session.

## Notes

- **A pull-request review is its own session,** separate from the working-tree one for the same repository, so it can never overwrite unfinished local work. Re-running the same PR resumes that PR's session; if the PR has new commits the server re-fetches, and if it does not, nothing is re-derived.
- **`/cloudaeye:implement` does not work on a pull-request review.** Its plans describe edits to a working tree, and the source for a PR lives on GitHub. If the user wants to fix what the review found, they check the branch out and review again locally. Say that rather than offering a plan that cannot be applied.
- Submit analysis once, resolve its response using **Queued Result**, report the output, then stop. No fix-and-retry loop inside the skill.
- **Bugs only.** This profile runs: logic errors, syntax/compile breaks, edge cases, input validation, concurrency safety, error handling, code clarity, naming consistency, and code signatures. Code signatures include a **compiler type check** over the AST graph, which catches callers broken by a changed definition even when those callers are in files this diff never touched — so a `code_signature` finding may point at a file you didn't edit. That's the point; don't dismiss it as out of scope. Security prompts are **not** part of it — they cost real tokens on every scanned file, so they are routed behind `/cloudaeye:security` (security surface only) and `/cloudaeye:review` (bugs + security). If the change touches authentication, input handling from untrusted sources, deserialization, secrets, crypto, LLM prompts, tool definitions, or agent orchestration, say so and suggest `/cloudaeye:security` — don't silently skip it, and don't run it uninvited.
- **Re-inspection is user-driven.** The user may say "fix issue X and run inspect again" — that's fine, just re-invoke this skill. The server resumes the same review session for the OAuth account and repository, so iteration continuity is server-handled. Your job on re-invocation is just to write a sharp intent (step 2) that describes only the most recent change.
- Pre-commit only: the diff is always `git diff` (working tree vs `HEAD`). Committing moves `HEAD`, but the review session persists — its recorded `head` is refreshed on the next call, and prior intent and task context carry across.
- If `inspect_diff` is unavailable (MCP not connected), warn the user and skip.
