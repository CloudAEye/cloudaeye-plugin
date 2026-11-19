---
name: ultrareview
description: Every CloudAEye review of a change in one run — the full review (bugs and security), the AI slop score, the change-risk verdict, the architecture review and the control-flow diagram, plus the PR checklist on a pull request and the task check when you name one. CloudAEye runs every pass on its side, once, in the order that lets later results reuse earlier ones, as one command billed once per run. The report opens with whether the change is approved for merge or needs a human review (with suggested reviewers when it does, on a pull request), then a results table, what to do next, and every command's full output saved to a file; on a pull request the same report is posted as one comment. It never edits code on its own. The most expensive CloudAEye command.
when_to_use: Only when the user types /cloudaeye:ultrareview or asks for every CloudAEye review at once. For one full review use /cloudaeye:review; for the routine check after a task use /cloudaeye:inspect.
argument-hint: "[path | #PR] [--critical|--high|--medium|--low] [--model MODEL] [--model-provider PROVIDER] [--invert-model true|false] [task:<ticket | issue URL | text>]"
disable-model-invocation: true
allowed-tools: ["Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__start_session", "mcp__cloudaeye__start_session", "mcp__plugin_cloudaeye_cloudaeye__ultrareview", "mcp__cloudaeye__ultrareview", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result", "mcp__plugin_cloudaeye_cloudaeye__inspect_diff", "mcp__cloudaeye__inspect_diff", "mcp__plugin_cloudaeye_cloudaeye__slop_score", "mcp__cloudaeye__slop_score", "mcp__plugin_cloudaeye_cloudaeye__check_pr", "mcp__cloudaeye__check_pr", "mcp__plugin_cloudaeye_cloudaeye__change_risk", "mcp__cloudaeye__change_risk", "mcp__plugin_cloudaeye_cloudaeye__review_arch", "mcp__cloudaeye__review_arch", "mcp__plugin_cloudaeye_cloudaeye__control_flow", "mcp__cloudaeye__control_flow", "mcp__plugin_cloudaeye_cloudaeye__check_task", "mcp__cloudaeye__check_task", "mcp__plugin_cloudaeye_cloudaeye__review_summary", "mcp__cloudaeye__review_summary", "mcp__plugin_cloudaeye_cloudaeye__assign_reviewer", "mcp__cloudaeye__assign_reviewer"]
---

## Queued Result

Step 3 submits **one** analysis, the ultrareview, and resolves it here. A
direct response without `job_id` uses step 3's output rules. An active
response (`queued`, `running`, `retrying`) without a non-empty `job_id` is
malformed.

For a queued response, keep its `job_id` and call
`mcp__plugin_cloudaeye_cloudaeye__get_job_result(job_id, wait_seconds=110, since=<progress_id>, report="ultrareview")`
using the submitting OAuth account while status is `queued`, `running`, or
`retrying`. `since` is the `progress_id` of the previous answer (empty on the
first call). The server keeps the call open while the job runs, so call again
straight away: no sleep, no pause between calls. In Claude Code the job's steps
show live under the call, and a long job takes a few calls; an answer reused
from an earlier run on this change comes back within a second.

**Show progress.** The developer may never have seen CloudAEye. Print each line
on its own, exactly as given, with no other words around it: no job ids, no
"polling", no commentary.

1. Right before submitting, print
   `⏳ CloudAEye is running every review of your change in one run. This usually takes several minutes; progress shows below.`
2. An answer that comes back still active carries `message`, one line saying
   what the job is doing now ("Step 3 of 5 · Reviewing files: 4 of 8 done · 48s"),
   and `progress_id`. Print `⏳ ` + `message` only when `progress_id` differs from
   the one you last printed; an answer where only the time moved prints
   nothing. Never invent a line the server did not send.
3. On `completed`, print `✅ CloudAEye finished.` and nothing else until the report.
4. A completed answer may carry `next_run`. Keep its entries. After the final
   report, end with the heading `**To get more from the next run**` and each
   distinct entry once, as a bullet, exactly as given, without restating it in
   your own words. With none, add no such section.

Stop after 200 calls or 55 minutes from submission, whichever comes first;
check the deadline before each call. On timeout or unavailable polling,
report the limitation and retain the ID for later. Never re-submit to check
progress or start replacement work automatically.

On `completed`, require a `result` dictionary and use it as **the result**,
preserving the tool's original fields. Completion is not a clean verdict: an
inner `status: error` is a run that failed (step 3 says how to report it).
Report missing/expired results, never treat them as empty or clean.

**A refusal ends the run.** An outer `failed` carrying `error_code`:

- `PAID_SWITCH_REQUIRED`: ultrareview is on paid plans only. Print the `error`
  as given, then say that `/cloudaeye:review`, the full review of bugs and
  security, is included in the free plan. Stop.
- `INSUFFICIENT_CREDITS`, `USAGE_LIMIT_REACHED`, `SPENDING_BLOCKED`, or any other
  code: print the `error` exactly as given and stop.

Any other outer `failed` or `error`: report it and stop. After a refusal or a
failure never fall back to the step-by-step flow, and never run any of the
commands ultrareview runs in its place: each is a command of its own.

**One job, once.** Submit the ultrareview once per run. Never call the tools it
runs (`inspect_diff`, `slop_score`, `check_pr`, `change_risk`, `review_arch`,
`control_flow`, `check_task`, `review_summary`, `assign_reviewer`) beside it: the
server runs them, and only the step-by-step guide calls them itself.

## The checks

One row per check in the settings (`## Ultrareview` > `### Checks`), in the same
order and with the same names, then the human review. CloudAEye runs them on its
side, top to bottom, in one command:

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
└── Human review    /cloudaeye:assign-reviewer   only when a human review is required; pull requests only; suggests, never requests
```

Bugs and Security are one review when both run, never two.

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
- The settings are read in step 1, and the server reads their checks itself. A
  check they turn off is not run: say once, *Turned off in the repository's
  settings: …*, and its row and its section in the report read *skipped: turned
  off in the repository's settings* (the settings guide printed with them says
  which). With Bugs or Security off, the review runs the other half alone.

## What the user typed

| Argument | What to do |
|---|---|
| *none* | The working tree: every uncommitted change. Go straight to **Steps**. |
| `#405`, or bare digits like `405` | A pull request. First run `sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide ultrareview-pull-request`: it changes steps 1 and 3 and the report. |
| a path: `src/auth/`, `src/auth/login.ts` | Only the changes under it. First run `sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide scoped-run`. Every verdict below then means *for that path*. |
| `task:…`, `--critical` `--high` `--medium` `--low`, `--model`, `--model-provider`, `--invert-model` | First run `sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide ultrareview-options`. These combine with any row above. |

Digits mean a pull request; a directory named `405` is written `./405`. Each guide is that one
command, alone in its Bash call; run the ones the arguments call for before step 1.

## Steps

### 1. One session, one upload

Every step below uses **this one session**. Never call `start_session` again
and never upload twice.

Set up the session.

Run exactly this one command, alone in its Bash call (that is what lets it run without asking the user for permission):

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae start --review --author --guide ultrareview-settings
```

Its first line is JSON. Call `mcp__plugin_cloudaeye_cloudaeye__start_session` with every field of that line, unchanged, and keep the answer as `SESSION`; its `session_id` is the one every later call takes.

- `SESSION.gate` is `repository`: the repository is not connected to CloudAEye yet. Run `sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide connect-repository` and follow it.
- The tool is unavailable, or `status` is `error`: stop and tell the user to authenticate CloudAEye through `/mcp`.
- `SESSION.upload_needed` is `false`: the server already has this exact change. Skip the upload.
- Otherwise upload the change: exactly this one command, alone in its Bash call, with `SESSION` as JSON inside single quotes. The script checks the values itself and never prints a token.

  ```bash
  sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae upload '<SESSION as JSON>' --review --guide ultrareview-settings
  ```

Read the summary lines — the upload's when it ran, the first command's when it was skipped — and don't re-derive them:

| output | what to do with it |
|---|---|
| `cloudaeye_error=…` | Stop and report it. Never print `upload_token` or `key_token`. |
| `diff_bytes=0` | Nothing pending — report "nothing to review" and stop. |
| `author=` | Your GitHub username, for the risk step and the verdict. Empty means leave `author` out: the server tries your sign-in. |
| `settings:` | The team's settings as JSON (`SETTINGS`). When any apply to this change, `settings-guide:` follows them and says what they turn off and what to pass; with none, nothing follows and every check runs. |
| `base_source=fork_point` | The right baseline. Say it in one short line and nothing more, with no code formatting: *Baseline: <branch> at its fork point.* Nothing more: `base_age` is how old <branch>'s newest commit is, not the fork point, and on a quiet repository an old one means nothing newer exists. |
| `base_source=head` | Degraded: only working-tree edits are in the diff. Say so. If `SESSION` carries `setup_required`, report its `reason` and `remedy` as written; never quote `target_branch_error`, which names an internal record. |
| `upload_http=` not `200` | The diff never reached the server. Stop; otherwise a stale result can look clean. |

**Which baseline applied must reach the user.** Every degradation still produces output that looks correct, so silence about it is the one failure mode that misleads.

### 2. Same change or new change — and one intent

The same change is one the server already holds: `SESSION.upload_needed` is
`false`, or the upload printed `diff_unchanged=true` (on a pull request,
`SESSION.diff_unchanged`).

**The same change:** everything that already ran on it is answered from what
is stored rather than run again. For that to happen the intent must not
change, so **pass no `intent` at all** — the session keeps the one the change
was reviewed with. Still run step 3: the server answers each pass from its
store when it can, and runs only what is missing. The one exception: if the
user asked you to leave a flagged finding alone, write a new intent that says
so — that reruns the review and the slop score, which is the point.

**A new change:** write one intent paragraph and pass it as `intent`.

- **Pull-request mode:** use the pull request's own title and description, and
  say in one line that the intent is the author's stated purpose.
- **Otherwise:** describe the code change you made in this round of edits —
  what and why, plus any security-relevant surface it touches. **Do not read
  the diff to write it.** If you did not make the changes, say so inside the intent itself and never to the user: your reply says nothing about the intent (not what it says, not that you wrote one, not who made the change), and take the file list from the `changed_files=` line — never run a git command for it, and never read the diff.

### 3. Run the ultrareview

**The step-by-step flow.** When `mcp__plugin_cloudaeye_cloudaeye__ultrareview` is
not among your tools (an older CloudAEye server), or it answers
`fallback: "steps"` (a public demo repository), run
`sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide ultrareview-steps` and follow it in
place of the rest of this step. Only then: never after a refusal or a failure.

Otherwise call `mcp__plugin_cloudaeye_cloudaeye__ultrareview` **once**, with:

| Argument | What to pass |
|---|---|
| `session_id` | `SESSION.session_id` |
| `intent` | Step 2's paragraph on a new change; nothing on the same change. |
| `policy` | `SETTINGS.ultrareview`, whole and as it is, when present; nothing otherwise. |
| `rules` | `SETTINGS.rules`, when there are any. |
| `author` | Working tree or path only: what step 1's `author=` line carries; nothing when that is empty, and never on a pull request. |
| `task_description`, `task_source` | Working tree or path only, from `task:`, as the options guide routes it. |
| `review_model`, `model_provider`, `invert_model`, `llm_key`, `min_severity` | Only what the options guide or the settings guide told you to pass; an option the user typed wins over the settings. |
| `depth`, `cross_repo` | From `SETTINGS.control_flow`, when the settings guide gave them. |
| `post` | `true` on a pull request (the PR number is the request to post: never ask); never on the working tree or a path. |
| `context` | The scope label below, when there is one. |

Leave out every argument that has nothing to pass. Never pass `profile`,
`review_config` or `report_types`: the server picks the review's half from the
Bugs and Security checks in `policy`, and runs or skips each pass by
`policy.checks`, so never skip or choose one yourself.

**Scope label.** In path mode, `context` is `{"scope_path": "<path>"}`. When
your settings left files out, the label says so too: `"<path, or the whole change>
except <the patterns, comma-separated>"`. Otherwise pass no `context`.

Resolve the job as **Queued Result** says. A direct answer with no `job_id`:

- `fallback: "steps"`: the step-by-step flow above.
- Anything else (`status: error`, or `unsupported` with no fallback): print its
  `error` as given and stop.

The completed `result`:

- `skipped: "empty_diff"`: there was nothing to review, and nothing was billed.
  Report "nothing to review" and stop.
- `status: "error"`: the review failed or was degraded, so there is no verdict.
  Report it as **4. The report** says for a run with no verdict: `error` as
  given, the *Steps:* line (a checklist that was started was still collected,
  and `steps.checklist` says so), and on a pull request the *Posted* line. Never
  call it clean.
- `status: "ok"`: write **4. The report**.

### 4. The report

The result's `card` is short text for a terminal, and `report` is the whole
ultrareview report as a file to save. Do not print the `card` (the pull-request
guide takes its reviewers line from it, and nothing else): the developer gets
everything in that file.

Print the report's top once, after the run, in this shape, and nothing
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

Steps: checklist ok · review ran (review) · slop ran · …

### What to do next

…the result's summary…
```

Then save the full report (exactly this one command, alone in its Bash call):

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae report ultrareview '<result.report as JSON>'
```

and end with `Full report, every command's output: <report_path>` (on
`report_error=…`, say it could not be saved and why). Never open, read or
print that file yourself. With no `result.report`, say the full report is not
available and why, and save nothing.

**Summary.** The result's `headline` **verbatim**, in bold, then its `reasons`
as a list (none when approved). Never write the headline yourself and never
soften it: it is decided by rule from what was stored, and no risk verdict at
all is a human review, never an approval. With no `headline` (`status:
"error"`), write *No verdict:* and the `error`, and write neither headline
yourself.

**Your settings** — only when settings applied: the settings guide has this block.

**Suggested reviewers** — only under *requires human review*:

- Assigning turned off (the result has `assign_reviewers: false`): one line,
  *Not assigned — assigning human reviewers is turned off in the repository's settings.*
- Pull request: the pull-request guide has these lines.
- Uncommitted changes or a path: *Suggested reviewers: open a pull request
  first, then `/cloudaeye:assign-reviewer #<PR number>` suggests who to assign
  it to.*

Under *approved for merge* there is no reviewers line.

**Results.** The result's `results` as a two-column table, one row per entry,
`criterion` and `assessment` **exactly as given**, in their order. Every
criterion is always there — AI slop score, Risk score, Bugs, Security, PR
checklist, Unit test coverage, Architecture, Control flow, Task. One this run
cannot have reads *not applicable* and why (the checklist before a pull
request, a task nobody named); one that should have run and did not reads
*not run*; one the settings switched off reads *turned off in the repository's settings*.
None is a pass, and they are different: never write one for another. Never add, drop, merge or recompute a row. Under the table, one line says what each pass
did: *Steps:* and each entry of `steps`, in its order, as its name and its
value exactly as given, joined with ` · `.

**What to do next.** The result's `summary` **verbatim** under the heading
`### What to do next`. Every line in it was checked against the results, and
its `#n` are the Review section's numbers; do not reword, re-order or add to
it. `cached: true` adds *(reused)* to the heading. When `summary` is empty,
write one line instead — *No summary:* and why (`unavailable`: `model_failed`
is the tenant's model not answering, `nothing_checked` is an answer that did
not survive the checks) — and never read that as a clean change: the sections
in the saved report still stand.

Rules for the top:

- Never reformat, re-order, round or summarise what a tool returned; never say
  how a score is built (no weights, points or thresholds).
- A pass whose `steps` entry says it failed or was unmeasured gets one line
  under the Results table saying which, as `steps` gives it.
- `steps.slop` reading `unmeasured`: say the AI slop score could not be measured,
  so risk will not approve automatically. **Name no reviewer except from the
  reviewers line**, as the pull-request guide says.

**After the report line, at most three lines:**

1. `/cloudaeye:implement` numbers refer to the **Review** section. The AI slop
   and architecture lists number their own findings; to act on one of those,
   run that command on its own first.
2. Pull-request mode: the pull-request guide has the closing line.
3. If there are findings, ask which (if any) to fix — "1 and 3", or
   `/cloudaeye:implement [1,3]` for a plan. Do not start editing until the user
   replies.

## Notes

- **Each pass runs once, and once per change.** inspect and security are inside
  the review; the slop score reuses the review; risk reuses the slop score, the
  checklist and the review. Run again on the same change — or after running any
  of these commands on their own — and what already ran is answered from what is
  stored; a new change runs again. Never re-submit to get a fresher answer on an
  unchanged change: it is the same answer.
- **On a pull request, the report is the one thing posted** besides the
  checklist's own comment: the server posts it once, editing the comment an
  earlier run left. On uncommitted changes or a path nothing is posted.
- **Reviewers are suggested, never requested.** The server suggests them only
  when the verdict is *requires human review*, on a pull request.
- **Your settings decide by rule, and only toward more review.** The limits and the
  checks are compared by the server; your instructions are read by a model that may
  only ask for more review or more reviewers. Change them with `/cloudaeye:config`.
- **Working tree is pre-commit:** the diff is `git diff` against the fork point.
  A pull-request run is its own session and never overwrites unfinished local
  work; `/cloudaeye:implement` does not apply to it.
- This is a single run: no fix-and-retry loop inside the skill. After fixes,
  the user runs it again (or just `/cloudaeye:review`), and what did not change
  is answered from what is stored.
- If the CloudAEye tools are unavailable (MCP not connected), warn the user and
  stop. Never judge the change yourself from `git diff` in its place.
- A bare `/ultrareview` is Claude Code's own command; this one is always
  `/cloudaeye:ultrareview`.
