---
name: review
description: Full CloudAEye review — bugs and security in one pass — of the uncommitted changes in this repo, of just one file or directory of them, or of an open pull request given its number. Reports findings with file, line and severity, grouped by kind; it never edits code on its own. The widest and most expensive of the CloudAEye passes.
when_to_use: "Use before opening a significant PR, when the user asks for a full, complete or thorough review, when they name a path to review (\"/cloudaeye:review src/auth/\"), or when they name a pull request (\"/cloudaeye:review #405\", \"review PR 12\"). For the routine check after finishing a task use /cloudaeye:inspect; for the security surface alone use /cloudaeye:security."
argument-hint: "[path | #PR] [--critical] [--model MODEL] [--model-provider PROVIDER] [--invert-model true|false]"
allowed-tools: Read, Grep, Glob, LS
---

## Queued Result

Submit the analysis once. An answer without `job_id` is the response itself
(report `status: error` and stop). With a `job_id`, call
`mcp__plugin_cloudaeye_cloudaeye__get_job_result(job_id, wait_seconds=110, since=<last progress_id>, report="review")`
again and again, with no pause, while `status` is `queued`, `running` or
`retrying`. The server keeps each call open while the job runs.

- Right before submitting, print:
  `⏳ CloudAEye is reviewing your change. This usually takes a few minutes; progress shows below.`
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

## When to run

The user invoked `/cloudaeye:review`, or asked for a full, complete or thorough review. This is the widest pass: everything `/cloudaeye:inspect` checks **plus** everything `/cloudaeye:security` checks, in one call, and it costs more than either. For the routine check after a coding task, `/cloudaeye:inspect` is the right skill.

## What the user typed

| Argument | What to do |
|---|---|
| *none* | The working tree: every uncommitted change. Go straight to **Steps**. |
| `#405`, or bare digits like `405` | A pull request. First read `${CLAUDE_PLUGIN_ROOT}/resources/skills/pull-request-run.md`, and follow it where it differs from the steps. |
| a path: `src/auth/login.ts`, `src/auth/` | Only the changes under it. First read `${CLAUDE_PLUGIN_ROOT}/resources/skills/scoped-run.md`. |
| `--critical` `--high` `--medium` `--low`, `--model`, `--model-provider`, `--invert-model` | First read `${CLAUDE_PLUGIN_ROOT}/resources/skills/review-flags.md`. These combine with any row above. |

Digits mean a pull request; a directory named `405` is written `./405`. Read the guides the
arguments call for, in one turn, before step 1.

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
   later call takes. In the same turn, Glob `**/.cloudaeye.config` and `**/.cloudaeye.rules` with `TOP` as
   the path: they are `SETTINGS_FILES`, each a path relative to `TOP`.

   - `SESSION.gate` is `repository`: the repository is not connected to CloudAEye yet. Read
     `${CLAUDE_PLUGIN_ROOT}/resources/skills/connect-repository.md` and follow it.
   - The tool is unavailable, or `status` is `error`: stop and tell the user to authenticate CloudAEye through `/mcp`.

   Upload the change with this one command, writing in `<TARGET>` (`SESSION.target_branch`),
   `<UPLOAD_URL>` and `<UPLOAD_TOKEN>` from `SESSION`, and one `-F 'settings_file=@<path>;filename=<path>'` for each of
   `SETTINGS_FILES`, at the end. It writes only under `.cloudaeye/`
   (which ignores itself) and leaves your git index as it was. It runs in `TOP`: when that is not
   the folder Claude Code is working in, put `cd '<TOP>' && ` in front of it. When `SESSION.target_branch` is
   empty, or the command stops at a `git` error before `curl` runs, read `${CLAUDE_PLUGIN_ROOT}/resources/skills/no-target-branch.md`
   instead.

   ```bash
   git -c credential.helper= fetch -q origin '<TARGET>' 2>/dev/null; mkdir -p .cloudaeye && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Upload-Token:%s"\n' '<UPLOAD_URL>' '<UPLOAD_TOKEN>' | tee .cloudaeye/upload.curl && git rev-parse --git-path index | xargs -I{} cp -p {} .cloudaeye/index && export GIT_INDEX_FILE=.cloudaeye/index && git add -N . && git diff --merge-base 'origin/<TARGET>' --output=.cloudaeye/session.diff -- . && git merge-base HEAD 'origin/<TARGET>' | curl -sS --fail-with-body -K .cloudaeye/upload.curl -F 'base_sha=<-' -F 'file=@.cloudaeye/session.diff' -F 'settings=review'
   ```

   It prints the upload's settings file, then the server's answer as JSON. Never print the upload token.

   | what came back | what to do with it |
   |---|---|
   | `curl: (22)` and an error | The diff never reached the server. Stop; otherwise a stale result can look clean. |
   | `diff_files` is `0` | Nothing pending — report "nothing to review" and stop. |
   | `settings` | The team's settings that apply to this change (`SETTINGS`). Read `${CLAUDE_PLUGIN_ROOT}/resources/skills/review-settings.md` and follow it. With no `settings`, none apply and nothing changes. |
   | `changed_files` | The changed paths (up to 20, `more_files` beyond). Take a file list from here, never from a git command of your own. |

   **Say which baseline applied:** the change against where this branch forked off
   `origin/<TARGET>`. Every degraded run still produces output that looks correct, so silence
   about it is the one failure mode that misleads.

2. Write a one-paragraph intent summary.

   **The same change as last time** (the upload answered `diff_unchanged: true`): **write no intent and pass none.** The session keeps the one this change was reviewed with, so the server answers from what it stored, in seconds and at no cost; a new paragraph, however close, reads as a new instruction and runs the whole review again. The one exception: the user asked you to leave a flagged finding alone, or to look at something else this time — then write a new intent that says so.

   **Otherwise** describe **the code change you just made in this round of edits** — what you implemented and why, plus any security-relevant surface it touches (untrusted input, auth, secrets, serialization, prompts, tool definitions). Not a re-statement of the original ask. The planner uses this verbatim to prioritise within the full category set, and it is the **only** channel for telling the reviewer to leave a previously-flagged issue alone — so if you are asking it to skip something, say which finding and why, in words the user can see.
   - **Do not read the diff to write this.** No `cat .cloudaeye/session.diff`, no `git diff`. You made these edits — the intent comes from your own working context, and the server is what analyses the diff. If you genuinely did not make the changes (a resumed session, or the user edited by hand), say so inside the intent itself, never as a line to the user, and take the file list from the upload's `changed_files` — never run a git command for it, and never read the diff.
3. Call CloudAEye's `inspect_diff` MCP tool (`mcp__plugin_cloudaeye_cloudaeye__inspect_diff`, Claude Code asks before its first use) with:
   - `session_id`: `SESSION.session_id`
   - `intent`: the summary from step 2; left out altogether for the same change as last time
   - `profile`: `"review"` — **always this value from this skill.** It selects every valid prompt: the bug categories and the full security surface.
   - whatever a guide you ran, or the `settings-guide:`, told you to pass: `min_severity`, `review_model`, `model_provider`, `invert_model`, `rules`, `llm_key`, `context.scope_path`. Pass none of them otherwise; never default to a floor or a model nobody asked for.
   - `context`: otherwise only `pr_title` / `pr_description`. Do not pass `review_config` or `report_types`; either one overrides the profile.

   You do **not** need to read the changed source files yourself before calling — the server has the post-edit contents staged and examines them with its own tooling.
4. Report the response to the user:
   - **First: `verdict` is `error`, or the response carries a `degraded` block.** The review ran with no post-edit source staged, so every prompt saw an empty file and the secret scan never picked a detector (`secret_scan.detector: "none"` is the tell). **Report it as a failed run and stop — do not present the findings, and never call it clean.** `degraded.cause` names the upstream reason when there is one; `context_refresh.status` of `skipped`/`failed` carries it verbatim, and an expired GitHub installation token is the usual culprit. The server does not cache a degraded run, so re-running once the cause is fixed gives a real review.
   - The `verdict` (`approve` / `request_changes`).
   - **Report what came back, not what didn't.** Don't list report types that produced no findings, don't quote timings, file counts or detector names that worked, and don't explain which prompts didn't fire. A diagnostic field the response *does* carry is there because it changes what the result means — those you report.
   - Every finding, **grouped by `report_type`** — leaked secrets first (a committed credential has a clock on it), then bugs, then application security, then LLM / AI-agent / MCP security. Within each group give file, line, severity, and message. The grouping is what makes a long list readable; don't flatten it.
   - **Print each finding with its `n`, exactly as the server numbered it** — `1.`, `2.`, `3.` — and never renumber. That number is what the user types back at `/cloudaeye:implement [1,3]`, and the server resolves it against its own stored report, so a list you renumbered would aim the fix at the wrong finding.
   - The `counts` roll-up, so the user sees the shape before the detail.
   - If there are findings, ask which (if any) to fix, and say they can answer with the numbers — "1 and 3", or `/cloudaeye:implement [1,3]` for a plan. Do not start editing until the user replies. After fixing, re-invoke this skill (the server resumes the same review session) and write a fresh intent naming the findings you addressed.

## Notes

- Submit analysis once, resolve its response using **Queued Result**, report the output, then stop. No fix-and-retry loop inside the skill.
- Expect more findings, and more low-severity ones, than `/cloudaeye:inspect`. Present them by severity within each report type so the user can triage rather than wade.
- **What it runs:** bugs (logic errors, compile breaks, edge cases, input validation, concurrency, error handling, clarity, naming, code signatures, performance, dead imports), application security, the LLM, AI-agent and MCP security surfaces — attached server-side only to files with matching evidence, so a repository with none of that code pays nothing for them — and secrets leaked on the changed lines.
- **Pre-commit:** the diff is `git diff` against the fork point. Committing moves `HEAD`, but the review session persists — its recorded `head` is refreshed on the next call, and prior intent carries across.
- If `inspect_diff` is unavailable (MCP not connected), warn the user and skip.
