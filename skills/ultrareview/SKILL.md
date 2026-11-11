---
name: ultrareview
description: Every CloudAEye review of a change in one run — the full review (bugs and security), the AI slop score, the change-risk verdict, the architecture review and the control-flow diagram, plus the PR checklist on a pull request and the task check when you name one. Each pass runs once, in the order that lets later results reuse earlier ones. The report opens with whether the change is approved for merge or needs a human review (with suggested reviewers when it does, on a pull request), then a results table, what to do next, and every command's full output in collapsible sections; on a pull request the same report is posted as one comment. It never edits code on its own. The most expensive CloudAEye command.
when_to_use: Only when the user types /cloudaeye:ultrareview or asks for every CloudAEye review at once. For one full review use /cloudaeye:review; for the routine check after a task use /cloudaeye:inspect.
argument-hint: "[path | #PR] [--critical|--high|--medium|--low] [--model MODEL] [--model-provider PROVIDER] [--invert-model true|false] [task:<ticket | issue URL | text>]"
disable-model-invocation: true
allowed-tools: ["Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__start_session", "mcp__cloudaeye__start_session", "mcp__plugin_cloudaeye_cloudaeye__inspect_diff", "mcp__cloudaeye__inspect_diff", "mcp__plugin_cloudaeye_cloudaeye__slop_score", "mcp__cloudaeye__slop_score", "mcp__plugin_cloudaeye_cloudaeye__check_pr", "mcp__cloudaeye__check_pr", "mcp__plugin_cloudaeye_cloudaeye__change_risk", "mcp__cloudaeye__change_risk", "mcp__plugin_cloudaeye_cloudaeye__review_arch", "mcp__cloudaeye__review_arch", "mcp__plugin_cloudaeye_cloudaeye__control_flow", "mcp__cloudaeye__control_flow", "mcp__plugin_cloudaeye_cloudaeye__check_task", "mcp__cloudaeye__check_task", "mcp__plugin_cloudaeye_cloudaeye__review_summary", "mcp__cloudaeye__review_summary", "mcp__plugin_cloudaeye_cloudaeye__assign_reviewer", "mcp__cloudaeye__assign_reviewer", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
---

## Queued Result

Every step below that calls a session tool submits **one** analysis and resolves
it here before the next step submits anything. A direct response without
`job_id` uses that step's output rules; report `status: error` and stop that
step. An active response (`queued`, `running`, `retrying`) without a non-empty
`job_id` is malformed.

For a queued response, keep its `job_id` and call
`mcp__plugin_cloudaeye_cloudaeye__get_job_result(job_id, wait_seconds=110, since=<progress_id>, report=<the step's name, see **4. The report**>)`
using the submitting OAuth account while status is `queued`, `running`, or
`retrying`. `since` is the `progress_id` of the previous answer (empty on the
first call). The server keeps the call open while the job runs, so call again
straight away: no sleep, no pause between calls. In Claude Code the job's steps
show live under the call, and a long job takes a few calls; an answer reused
from an earlier run on this change comes back within a second.

**Show progress.** The developer may never have seen CloudAEye, and each job's
steps count from one again, so say which part is starting. Print each line on
its own, exactly as given, with no other words around it: no job ids, no
"polling", no commentary.

1. Right before submitting a job, print `⏳ Now: <its row's name in the tree>`,
   for example `⏳ Now: AI slop score`.
2. An answer that comes back still active carries `message`, one line saying
   what the job is doing now ("Step 3 of 5 · Reviewing files: 4 of 8 done · 48s"),
   and `progress_id`. Print `⏳ ` + `message` only when `progress_id` differs from
   the one you last printed; an answer where only the time moved prints
   nothing. Never invent a line the server did not send.
3. A completed answer may carry `next_run`. Keep its entries as you go. After
   the final report, end with the heading `**To get more from the next run**`
   and each distinct entry once, as a bullet, exactly as given, without
   restating it in your own words. With none, add no such section.

Stop after 150 calls or 30 minutes from submission, whichever comes first;
check the deadline before each call. On timeout or unavailable polling,
report the limitation and retain the ID for later. Never re-submit to check
progress or start replacement work automatically.

On `completed`, require a `result` dictionary and use it as **the response**
for that step, preserving the tool's original fields. Completion is not a clean
verdict: report an inner `status: error` as a refusal. Stop on outer `failed`
or `error`; report missing/expired results, never treat them as empty or clean.

**One job at a time is what makes this command cheap.** Each job works on a
snapshot of the session taken when it is submitted, so a job submitted before
the previous one finished cannot see — and will pay again for — what that one
produced. Never submit two session jobs together. A job that is still pending
at its deadline ends the session chain: report every later step as *not run*
and keep the job id.

## The checks

One row per check in the settings (`## Ultrareview` > `### Checks`), in the same
order and with the same names, then the human review. They run top to bottom:

```text
/cloudaeye:ultrareview [path | #PR] [task:…]
├── PR checklist    /cloudaeye:check             pull requests only; supplies unit-test coverage, posts its own comment
├── Bugs            /cloudaeye:review            the review's bug half
├── Security        /cloudaeye:review            the review's security half, leaked secrets included
├── AI slop score   /cloudaeye:slop-score        reuses the review's work
├── Risk score      /cloudaeye:risk-score        reads the rows above; decides the approval verdict
├── Architecture    /cloudaeye:review-arch       what the change does to the architecture
├── Control flow    /cloudaeye:control-flow      calls added, removed or moved
├── Task check      /cloudaeye:check-task        only with task:…; uncommitted changes only
└── Human review    /cloudaeye:assign-reviewer   only when a human review is required; pull requests only
```

Bugs and Security are one review call when both run, never two.

Before anything runs, print this tree for the chosen mode with each row marked
**runs** or **skipped** with its reason:

- **PR checklist** needs a pull request. On uncommitted changes or a path it is
  *skipped: pull requests only*, and **Risk score** still runs — on your change
  before it is pushed, with you as the author and unit-test coverage reported as
  not measured.
- **Task check** runs only when the user gave `task:`, and only outside
  pull-request mode (*skipped: uncommitted changes only*).
- **Human review** is marked **only if a human review is required**: it runs
  when the verdict at the end is *requires human review*, never when the change
  is approved for merge, and only on a pull request (on uncommitted changes:
  *skipped: needs a pull request*). With **Auto-assign human reviewer** false in
  the repository's settings it never runs (*skipped: turned off in the repository's
  settings*).
- The settings are read in step 1. A check they turn off is not run: say once,
  *Turned off in the repository's settings: …*, and its row and its section in the
  report read *skipped: turned off in the repository's settings* (see **Your
  settings** below). With Bugs or Security off, the review runs the other half alone.

In pull-request mode, say once under the tree: *the report is posted on the
pull request as one comment, as the other commands post their cards, and
edited in place when you run this again; the PR checklist keeps its own
comment, as `/cloudaeye:check` always does.*

## Arguments

Read them in this order:

1. **`task:`** — everything after `task:` to the end of the input is the task,
   verbatim. Route it as `/cloudaeye:check-task` does: GitHub issue URL →
   `task_source="github-issue"`, the URL as `task_description`; Jira keys
   (`\b[A-Z][A-Z0-9]+-\d+\b`, brackets stripped, comma-separated) →
   `task_source="jira"`; anything else → `task_source="user-text"`, the text
   verbatim. Never summarise it.
2. **Model options** — `--model` → `review_model`, `--model-provider` →
   `model_provider`, `--invert-model` → `invert_model` (boolean `true` or
   `false`, never a string). They apply to **the review only**. One the user
   did not give comes from the repository's LLM settings when they set it (see
   **Your settings**), and is omitted otherwise. Reject a missing value, an
   unknown flag or another inversion value before initializing anything.
3. **Severity floor** — `--critical`, `--high`, `--medium` or `--low` →
   `min_severity` with the dashes stripped, for **the review only**. When one is
   given, say once: *the floor narrows the review, so the AI slop score cannot
   reuse it and runs its own pass.* An unrecognised value is refused by the
   server; report it rather than retrying without the floor.
4. **Mode**, from what remains:

   | Argument | Mode |
   |---|---|
   | *none* | **Working tree** — every uncommitted change. |
   | `#405`, or bare digits like `405` | **Pull request** — PR 405 of this repository. |
   | anything else — `src/auth/`, `src/auth/login.ts` | **Path** — only the changes under that file or directory. |

   Digits mean a pull request; a directory named `405` is written `./405`.

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
repository (`/cloudaeye:config` writes them): one at the root, and any in a directory
cover that directory and below. Step 1 reads the ones that apply to this change's
files — from the working tree before a commit, from the pull request's **target
branch** on a pull request, so a pull request cannot change its own settings — and
prints them as JSON after `settings:`. Keep that JSON as `SETTINGS`. With no files it
holds only empty `rules` and changes nothing. `error` means they could not be read:
say so in one line and run on CloudAEye's defaults. Say once, a line each:

- `applied` — the files that decided this run (*Using your settings from
  `.cloudaeye.config` and `services/payments/.cloudaeye.config`*);
- each of `problems` — a line a file could not read, whose default stands;
- `pending` (pull requests only) — *This pull request changes <files>; CloudAEye uses
  them once they are merged into <target>*;
- `fetched: false` — *<target> could not be fetched; read from your last copy of it*.

What they decide:

- **`SETTINGS.ultrareview.checks`** — a check set to `false` is not run: skip its
  step below. Bugs, Security, AI slop and risk are what an approval rests on: with
  any of them false, the verdict is a human review. Bugs and Security are the two
  halves of the review in step 2, and pick its profile: both true (or unset)
  `"review"`; Bugs false `"security"`; Security false `"bugs"`; both false, skip
  steps 2 and 9 (the AI slop score runs its own pass).
- **`SETTINGS.ultrareview`** — the checks, hard limits, `assign_reviewers`,
  `max_reviewers` and the instructions (a paragraph a settings file) — goes whole,
  as it is, as `policy` to `review_summary` (steps 10 and 12). Leave `policy` out
  when it is absent.
- **`SETTINGS.review`'s LLM settings** — for the review in step 2 only, each when
  the user gave no option for it: `model` as `review_model`, `provider` as
  `model_provider` (present only with `llm` set to `your own`), `invert_model` as
  `invert_model`. Say once which came from the settings. An option the user typed
  always wins. **An API key** in the settings is sent to CloudAEye by step 1 itself:
  `SETTINGS.review.api_key` says only where it comes from, whether it was found and
  whether it was `sent`. Never read, print or repeat the key, and never pass it to a tool.
- **`SETTINGS.rules`** — the team's review rules — go as `rules` to the review
  (step 2) when there are any.
- **Paths never reviewed** — step 1 leaves them out of the uploaded change, before a
  commit only; on a pull request the server reads the whole pull request.
- **`SETTINGS.control_flow`** — for step 7: `effort` as `depth` (`low` 1, `medium` 2,
  `high` 3) and `cross_repo` as it is.
- **`SETTINGS.review.severity_floor` is not used here**: the AI slop score cannot
  reuse a review run with a floor, and would pay for its own.

### 1. One session, one upload

Every step below uses **this one session**. Never call `start_session` again
and never upload twice.

The initialization gate already printed the current `branch` and `head`.

Call `mcp__plugin_cloudaeye_cloudaeye__start_session` with `INIT.repo_full`,
`branch` and `head` — no `language`. If the tool is unavailable, stop and tell
the user to authenticate CloudAEye through `/mcp`.

**Pull-request mode:** also pass `pr_number` — the digits, `#` stripped — and
skip the upload below; the server fetched the diff itself. On `status: error`,
print the `error` as written and stop: it is the eligibility refusal (closed,
wrong base branch, fork, over 50 files), and each names a different thing to
do. Never review the working tree instead. On success, say which pull request
this is (number, title, head SHA) and whether it is a draft. Then read your
settings as the target branch has them: exactly this one command, alone in its Bash call,
with `start_session`'s whole answer as JSON inside single quotes:

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae pr-settings '<the start_session answer as JSON>' --review
```

**Working-tree and path modes only, to the end of step 1.** Upload the change: exactly this one command, alone in its Bash call, with `start_session`'s whole answer as JSON inside single quotes. The script checks the values itself and never prints a token.

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae upload '<the start_session answer as JSON>' --review
```

Add `--scope '<the path>'` after the JSON when the user scoped the run to a path.

Read the two summary lines and the `start_session` result; don't re-derive them:

| output | what to do with it |
|---|---|
| `start_session` unavailable or `status: error` | Stop and tell the user to authenticate CloudAEye through `/mcp`. |
| `cloudaeye_error=…` | Stop and report it. Never print `upload_token` or `key_token`. |
| `diff_bytes=0`, `scope=-` | Nothing pending — report "nothing to review" and stop. |
| `diff_bytes=0` with a scope | Nothing has changed under that path. Say so **naming the path**, and stop. Never widen to the whole change. |
| `diff_files` below `total_files` | A scoped run. Report both — "reviewed 2 of 7 changed files (src/auth/)" — and say the cross-file checks cannot see the excluded files. Every verdict below means *for that path*. |
| `skipped_by_settings` above `0` | Your settings left that many changed files out (`SETTINGS.review.skip`). Say so, naming the patterns, and pass the label below as `scope_path`. |
| `settings:` | `SETTINGS` — see **Your settings** above. |
| `cloudaeye_error=scope_outside_repo` | The path escaped the repository. Report it and stop. |
| `base_source=fork_point` | Correct baseline. Name the branch and `base_age`. |
| `base_source=head` | Degraded: only working-tree edits are in the diff. Say so. If `start_session` returned `setup_required`, report its `reason` and `remedy` verbatim; never quote `target_branch_error`. |
| `upload_http=` not `200` | The diff never reached the server. Stop. |
| `diff_unchanged=true` | **The same change as last time** — see step 2. |

**Which baseline applied must reach the user.** Every degradation still produces output that looks correct, so silence about it is the one failure mode that misleads.

### 2. Same change or new change — and one intent

`diff_unchanged` decides it: the upload's summary line in working-tree and path
modes, the `start_session` response in pull-request mode.

**The same change (`true`):** everything that already ran on it is answered
from what is stored, and costs nothing. For that to happen the intent must not
change, so **pass no `intent` at all** to `inspect_diff` and `check_task` — the
session keeps the one the change was reviewed with. Still call every step
below: each tool answers from its store (`cached: true`, or `reused: true` from
the checklist) when it can, and runs only what is missing. The one exception: if
the user asked you to leave a flagged finding alone, write a new intent that
says so — that reruns the review and the slop score, which is the point.

**A new change (`false` or `unknown`):** write one intent paragraph and pass the
**identical text** to every tool below that takes one. Changing it between
steps invalidates the stored results the later steps reuse.

- **Pull-request mode:** use the pull request's own title and description, and
  say in one line that the intent is the author's stated purpose.
- **Otherwise:** describe the code change you made in this round of edits —
  what and why, plus any security-relevant surface it touches. **Do not read
  the diff to write it.** If you did not make the changes, say so inside the intent
  itself, never as a line to the user, and use `git diff --stat` for the file list — never the full diff.

### 3. Run, bottom-up

After each step print one progress line — `review: request_changes, 7 findings`,
or `review: reused — request_changes, 7 findings` when the response carries
`cached: true` (`reused: true` for the checklist) — and nothing more. The full
report is printed once, at the end.

**Scope label.** In path mode, `context` below is `{"scope_path": "<path>"}`. When
your settings left files out, the label says so too: `"<path, or the whole change>
except <the patterns, comma-separated>"`. Otherwise pass no `scope_path`.

1. **Start the checklist** (pull-request mode, unless turned off). Call
   `mcp__plugin_cloudaeye_cloudaeye__check_pr` with `repo`: `INIT.repo_full`,
   `pr_number`, `wait_seconds: 1` and `detail: true` (the full report, coverage
   by function included, comes back in `report`). It runs on the hosted service beside the
   session, so it starts first and is collected in step 4. Keep its
   `review_id`. `not_configured`, or an error, goes into the Check section and
   does not stop the run. Never start a second checklist. `status: "ok"` with
   `reused: true` means it already ran at this commit — nothing was billed or
   posted again, its report is already on the pull request, and step 4 is
   skipped.
2. **The review** (unless Bugs and Security are both turned off; then skip this
   step and step 9 — the AI slop score runs its own pass). Call
   `mcp__plugin_cloudaeye_cloudaeye__inspect_diff` with `session_id`, `intent`,
   `profile` — `"review"`, or `"security"` / `"bugs"` when the settings turn the
   other half off (see **Your settings**) — `min_severity`, the model options
   (the user's, else the settings'), `rules`: `SETTINGS.rules` when there are
   any, `llm_key: true` only when `SETTINGS.review.api_key.sent` is `true` and
   `model_provider` is the settings' provider, and `context` (the scope label).
   Never pass `review_config` or `report_types`.
   `rules_problems` in the answer names rules left out; say so in the Review section.
   **If it returns verdict `error` or a `degraded` block, the run failed:**
   every later step reads the same staged source. Still collect the checklist
   if one was started (step 4) — it is already paid for — then report the
   failure (`degraded.cause`, `context_refresh` verbatim) and stop. Never call
   it clean.
3. **The AI slop score** (unless turned off). Call `mcp__plugin_cloudaeye_cloudaeye__slop_score`
   with `session_id` and `context` (the scope label). Never
   `run_review: false`. It reuses what the review just computed.
4. **Collect the checklist** (pull-request mode, when step 1 returned a
   `review_id`). Call `check_pr` with `repo`, `pr_number`, that `review_id`
   and `detail: true`. On `pending`, call again with the same `review_id`, at most
   three calls in all; if it is still pending, keep the `review_id` for the
   Check section and say risk may measure coverage on its own. Collecting it is
   what posts it, and risk reads its unit-test coverage from that comment.
5. **Change risk** (every mode, unless turned off). Call
   `mcp__plugin_cloudaeye_cloudaeye__change_risk` with `session_id` and
   `post: false`. It reads the slop score, the checklist's coverage and the
   review's Critical findings instead of measuring them again. A slop score
   that failed does not stop this step: risk reports it unmeasured and will not
   approve automatically. **On the working tree or a path** the author is you:
   first run

   ```bash
   sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae login
   ```

   and pass `author`, what it prints after `author=`; omit it when that is empty
   (the server tries your sign-in). There is no checklist there, so coverage is
   reported as not measured, and the card is never posted.
6. **Architecture** (unless turned off). Call `mcp__plugin_cloudaeye_cloudaeye__review_arch` with
   `session_id`, `post: false`, and `context` (the scope label).
7. **Control flow** (unless turned off). Call `mcp__plugin_cloudaeye_cloudaeye__control_flow` with
   `session_id`, `post: false`, and `context` (the scope label), plus `depth` (from
   `SETTINGS.control_flow.effort`) and `cross_repo` when set. Leave `label` at its default.
8. **Task** (working-tree and path modes, with `task:`, unless turned off). Call
   `mcp__plugin_cloudaeye_cloudaeye__check_task` with `session_id`,
   `task_description`, `task_source` and the **same** `intent`.
9. **Hand the fix list back to the review.** Repeat step 2's call with
   identical arguments. It is answered from the stored review without running
   anything, and it makes `/cloudaeye:implement [1,3]` resolve against the
   Review section's numbers — the slop and architecture steps each saved a
   numbered list of their own after it. Do not print its result.
10. **The verdict, the results and what to do next.** Call
    `mcp__plugin_cloudaeye_cloudaeye__review_summary` with `session_id`,
    `policy`: `SETTINGS.ultrareview` when present, and — on the working tree or a
    path — `author`: the login step 5's command printed (run it here when risk
    was turned off).
    It reads every result stored above and returns the report's top: `headline`
    (approved for merge, or requires human review), `verdict` (`approve` or
    `review`), `reasons`, the `results` table and the `summary` of next steps;
    under `review`, `reviewers` (how many people: one, or more when an instruction
    asks, never above your maximum — `reviewers_capped` says when an instruction
    asked for more) and `reviewer_note` (who they should be, from your
    instructions). With settings it also returns `settings`
    (what was applied), `instructions` (each applied or not, and why) and
    `policy_problems`. It runs no review and decides by rule: your instructions can
    only ask for more review. Call it even when a step after the review failed — it
    reports what did run — but not when the chain stopped on a pending job or a
    failed review.
11. **Suggested reviewers — only when a human review is required.** When step
    10's `verdict` is `review` **and** this is a pull request **and** step 10 did
    not return `assign_reviewers: false` (your settings turned assigning off), call
    `mcp__plugin_cloudaeye_cloudaeye__assign_reviewer` with `repo`:
    `INIT.repo_full`, `pr_number`, `require_owners: false`, `count`: step 10's
    `reviewers`, and `note`: step 10's `reviewer_note` when there is one. It answers
    directly (no job) and requests nothing. Keep its `card` and the people in
    `recommended`; the server keeps the same suggestion for the pull
    request comment, so nothing is passed on. Never call it when the verdict is
    `approve`, and never with `apply: true` — a review request notifies people,
    and only the user asks for that. An error goes into the reviewers line and
    does not stop the run. On uncommitted changes or a path it does not run:
    there is no pull request to suggest reviewers for.
12. **Post the report — always, in pull-request mode.** A PR number means the
    report goes on the pull request as a GitHub comment, like every other
    command's card. Once step 10 has answered — and step 11, when it ran —
    call `review_summary` again with `session_id`, `post: true` and the **same**
    `policy` and `author` as step 10. The
    comment's suggested reviewers, and their card collapsed under them, come
    from step 11's call at this commit. Do this whatever the verdict,
    even when `summary` is empty or a step after the review failed — the
    comment says what did and did not run. It answers from step 10's stored
    summary without calling the model again, posts the whole report as one
    comment — or edits the one an earlier run posted — and returns `posted`.
    Never ask before posting: the PR number is the request. Never post on
    uncommitted changes or a path.

A step that fails, refuses or times out is reported in its own section. A
failure ends only that step, except that a session job still pending at its
deadline ends the chain (see Queued Result).

### 4. The report

**Every `get_job_result` call in this skill passes `report`**: the step's own
command name (`review`, `slop-score`, `risk-score`, `review-arch`, `control-flow`), and
`ultrareview` on step 10. Each answer then carries its card as short text, and
step 10's carries `report`, the whole ultrareview report as a file to save.
Do not print any step's card: the developer gets them all in that file.

Print the report's top once, after the last step, in this shape, and nothing
below it but the lines this section names:

```markdown
## Summary

**This code change requires human review.**

- The review found 2 High-severity security findings (#8: …)

**Suggested reviewers:** Alice Smith (`alice`) — Auth API owner · `bob` — main contributor to src/api/

## Results

| Review criteria | Assessment |
|---|---|
| AI slop score | 🟠 70/100 · High likelihood of low-quality code |
| … one row per criterion, as given … | |

Ran now: … · Reused from earlier runs on this change: …

### What to do next

…step 10's summary…
```

Then save the full report (exactly this one command, alone in its Bash call):

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae report ultrareview '<step 10's result.report as JSON>'
```

and end with `Full report, every command's output: <report_path>` (on
`report_error=…`, say it could not be saved and why). Never open, read or
print that file yourself.

**Summary.** Step 10's `headline` **verbatim**, in bold, then its `reasons`
as a list (none when approved). Never write the headline yourself and never
soften it: it is decided by rule from what was stored, and no risk verdict at
all is a human review, never an approval. If step 10 did not answer, write
*No verdict:* and why, and write neither headline yourself.

**Your settings** — when step 10 returned `settings`: one line, *Decided with your
settings* (the files in `SETTINGS.applied`, and *as on <target>* on a pull request)*:*
the hard limits (risk *n*/100, AI slop *n*/100, review severity), the most human
reviewers to assign (`max_reviewers`, or *assigning turned off* when `settings` has
`assign_reviewers: false`) and the checks turned off, as `settings` gives them. Under it, each of `instructions` — the instruction in quotes, *applied* or *not
applied*, and its `why` — then, when step 10 returned `reviewers_capped`, *an
instruction asked for <asked> reviewers; your settings assign at most <max>*, and each
of `policy_problems` (a setting that was left out). Never print this block when there
were no settings.

**Suggested reviewers** — only under *requires human review*:

- Assigning turned off (step 10 returned `assign_reviewers: false`): one line,
  *Not assigned — assigning human reviewers is turned off in the repository's settings.*
- Pull request, step 11 ran: the people in `recommended` — step 10's `reviewers`
  of them, in order — as `name` (`login`) — `role`, taken from `candidates`, never
  @-mentioned (a mention notifies them). When fewer were found than asked for,
  say how many were. Add
  one line: *a suggestion — no review has been requested;
  `/cloudaeye:assign-reviewer #<n>` asks for them when you want it.* Then,
  right under it in the Summary, a small collapsible
  `<details><summary>How they were suggested (/cloudaeye:assign-reviewer)</summary>`
  holding step 11's `card` verbatim in a ```text fence: who, why, their review
  queue and the review focus. It is the only place the card is printed.
- Pull request, step 11 failed: *none could be suggested* and its `error`.
- Uncommitted changes or a path: *Suggested reviewers: open a pull request
  first, then `/cloudaeye:assign-reviewer #<PR number>` suggests who to assign
  it to.*

Under *approved for merge* there is no reviewers line.

**Results.** Step 10's `results` as a two-column table, one row per entry,
`criterion` and `assessment` **exactly as given**, in their order. Every
criterion is always there — AI slop score, Risk score, Bugs, Security, PR
checklist, Unit test coverage, Architecture, Control flow, Task. One this run
cannot have reads *not applicable* and why (the checklist before a pull
request, a task nobody named); one that should have run and did not reads
*not run*; one the settings switched off reads *turned off in the repository's settings*.
None is a pass, and they are different: never write one for another. Never add, drop, merge or recompute a row. Under the table, one line says what this
run paid for: *Ran now: … · Reused from earlier runs on this change: …* (or
*Everything was reused — nothing ran again* when every step was). Risk is
re-read each time: it runs no AI once the slop score and the checklist are
reused, and its bug history moves with the day.

**What to do next.** Step 10's `summary` **verbatim** under the heading
`### What to do next`. Every line in it was checked against the results, and
its `#n` are the Review section's numbers; do not reword, re-order or add to
it. `cached: true` adds *(reused)* to the heading. When `summary` is empty,
write one line instead — *No summary:* and why (`unavailable`: `model_failed`
is the tenant's model not answering, `nothing_checked` is an answer that did
not survive the checks) — and never read that as a clean change: the sections
below still stand.

**Posted.** In pull-request mode, one line under *What to do next* from step
12's `posted`: `ok` → *Posted on the pull request:* the link (`url`), saying
*updated in place* when `edited` is true and *unchanged* when `unchanged` is;
`failed` or `unavailable` → *Not posted on the pull request:* and its `note`;
`unknown` → that delivery could not be confirmed and it will not be retried
automatically — check the pull request before running again. When step 12
never ran — the review failed, or a job was still pending at its deadline —
say so in this line: *Not posted on the pull request: the run did not finish*,
and why. Never leave a pull-request run without this line.

Rules for the top:

- Never reformat, re-order, round or summarise what a tool returned; never say
  how a score is built (no weights, points or thresholds).
- A step that failed, refused or timed out gets one line under the Results
  table saying which and why (`unavailable`, `degraded`, `context_refresh.reason`
  as given). Its row already says *not run*.
- `unmeasured` on the slop or risk result: say the score covers only what could
  be measured. **Name no reviewer from the risk result**; reviewers come from
  step 11 alone.

**After the report line, at most three lines:**

1. `/cloudaeye:implement` numbers refer to the **Review** section. The AI slop
   and architecture lists number their own findings; to act on one of those,
   run that command on its own first.
2. Pull-request mode: end with the link `[<repo>#<pr_number>](<pr_url>)`, where
   the report now sits.
3. If there are findings, ask which (if any) to fix — "1 and 3", or
   `/cloudaeye:implement [1,3]` for a plan. Do not start editing until the user
   replies.

## Notes

- **Each pass runs once, and once per change.** inspect and security are inside
  the review; the slop score reuses the review; risk reuses the slop score, the
  checklist and the review. Run again on the same change — or after running any
  of these commands on their own — and what already ran is answered from what is
  stored; a new change runs again. Never re-submit a step to get a fresher
  answer on an unchanged change: it is the same answer.
- **On a pull request, the report is the one thing posted** besides the
  checklist's own comment: `post` is `false` on every other session tool here,
  and `review_summary` posts once, editing the comment an earlier run left. On
  uncommitted changes or a path nothing is posted.
- **Reviewers are suggested, never requested.** `assign_reviewer` runs only when
  the verdict is *requires human review*, and never with `apply`.
- **Your settings decide by rule, and only toward more review.** The limits and the
  checks are compared by the server; your instructions are read by a model that may
  only ask for more review or more reviewers. Change them with `/cloudaeye:config`.
- **Working tree is pre-commit:** the diff is `git diff` against the fork point.
  A pull-request run is its own session and never overwrites unfinished local
  work; `/cloudaeye:implement` does not apply to it.
- This is a single run: no fix-and-retry loop inside the skill. After fixes,
  the user runs it again (or just `/cloudaeye:review`), and what did not change
  is answered from what is stored.
- If a tool is unavailable (MCP not connected), warn the user and stop. Never
  judge the change yourself from `git diff` in its place.
- A bare `/ultrareview` is Claude Code's own command; this one is always
  `/cloudaeye:ultrareview`.
