# Ultrareview step by step (only when the `ultrareview` tool is missing or answered `fallback: "steps"`)

This server cannot run ultrareview as one command (it is an older server, or the repository is a
public demo), so its passes run here, one command each, in place of the skill's step 3. The skill's
steps 1 and 2 stand as they are. Work out step 3's arguments first, as the skill and its guides say
(`intent`, `policy`, `rules`, the task, the model options, `llm_key`, `min_severity`, `depth`,
`cross_repo`, the scope label), then hand each to the step below that takes it. Never call
`ultrareview` again in this run.

## One job at a time

Every step below that calls a session tool submits **one** analysis and resolves it as the skill's
**Queued Result** says before the next step submits anything, with these differences:

- A direct response without `job_id` uses that step's output rules; report `status: error` and
  stop that step.
- Each `get_job_result` call passes `report`: the step's own command name (`review`, `slop-score`,
  `risk-score`, `review-arch`, `control-flow`), and `ultrareview` on step 10. Each answer then
  carries its card as short text, and step 10's carries `report`, the whole ultrareview report as a
  file to save. Do not print any step's card: the developer gets them all in that file.
- Right before submitting a job, print `⏳ Now: <its row's name in the tree>`, for example
  `⏳ Now: AI slop score`, in place of the skill's opening line and its `✅` line.
- Keep every job's `next_run` entries as you go; they are printed once, after the report.
- **One job at a time is what makes this cheap.** Each job works on a snapshot of the session taken
  when it is submitted, so a job submitted before the previous one finished cannot see — and will
  pay again for — what that one produced. Never submit two session jobs together. A job that is
  still pending at its deadline ends the session chain: report every later step as *not run* and
  keep the job id.

## Where step 3's arguments go

| Argument | Step below |
|---|---|
| `intent` | 2 and 9 (`inspect_diff`) and 8 (`check_task`): the **identical text** each time — changing it between steps invalidates the stored results the later steps reuse — and none at all on the same change |
| `rules`, `review_model`, `model_provider`, `invert_model`, `llm_key`, `min_severity` | 2 and 9, the review only |
| `policy` | 10 and 12 |
| `task_description`, `task_source` | 8 |
| `depth`, `cross_repo` | 7 |
| `context` (the scope label) | 2, 3, 6, 7 and 9 |
| `post` | none: only step 12 posts, on a pull request |

No step takes `author`: the server finds you from your CloudAEye sign-in.

**The checks are yours to read in this flow.** `policy.checks` (`SETTINGS.ultrareview.checks`): a
check set to `false` is not run, so skip its step below. Bugs and Security are the two halves of the
review in step 2, and pick its `profile`: both true (or unset) `"review"`; Bugs false `"security"`;
Security false `"bugs"`; both false, skip steps 2 and 9 (the AI slop score runs its own pass).

On the same change, still call every step below: each tool answers from its store (`cached: true`,
or `reused: true` from the checklist) when it can, and runs only what is missing.

## Step 3 in this flow: run, bottom-up

After each step print one progress line — `review: request_changes, 7 findings`,
or `review: reused — request_changes, 7 findings` when the response carries
`cached: true` (`reused: true` for the checklist) — and nothing more. The full
report is printed once, at the end.

1. **Start the checklist** (pull-request mode, unless turned off). Call
   `mcp__plugin_cloudaeye_cloudaeye__check_pr` with `repo`: `SESSION.repo_full`,
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
   `profile`: `"review"` unless the checks above say otherwise, what step 3's
   arguments hold for the review (`min_severity`, the model options, `rules`,
   `llm_key`), and `context` (the scope label).
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
   approve automatically. Pass no `author`: on the working tree or a path the server
   finds you from your sign-in, and on a pull request the author is the pull request's.
   On the working tree or a path there is no checklist, so coverage is reported as not
   measured, and the card is never posted.
6. **Architecture** (unless turned off). Call `mcp__plugin_cloudaeye_cloudaeye__review_arch` with
   `session_id`, `post: false`, and `context` (the scope label).
7. **Control flow** (unless turned off). Call `mcp__plugin_cloudaeye_cloudaeye__control_flow` with
   `session_id`, `post: false`, and `context` (the scope label), plus `depth` and `cross_repo` when the settings guide gave them. Leave `label` at its default.
8. **Task** (working-tree and path modes, with `task:`, unless turned off). Call
   `mcp__plugin_cloudaeye_cloudaeye__check_task` with `session_id`,
   `task_description`, `task_source` and the **same** `intent`.
9. **Hand the fix list back to the review.** Repeat step 2's call with
   identical arguments. It is answered from the stored review without running
   anything, and it makes `/cloudaeye:implement [1,3]` resolve against the
   Review section's numbers — the slop and architecture steps each saved a
   numbered list of their own after it. Do not print its result.
10. **The verdict, the results and what to do next.** Call
    `mcp__plugin_cloudaeye_cloudaeye__review_summary` with `session_id` and
    `policy`: `SETTINGS.ultrareview` when present.
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
11. **Suggested reviewers — pull requests only, and only when a human review is
    required.** When step 10's `verdict` is `review` **and** this is a pull request **and**
    step 10 did not return `assign_reviewers: false` (your settings turned assigning off), call
    `mcp__plugin_cloudaeye_cloudaeye__assign_reviewer` with `repo`:
    `SESSION.repo_full`, `pr_number`, `require_owners: false`, `count`: step 10's
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
    `policy` as step 10. The
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
deadline ends the chain (see **One job at a time**).

On a pull request, `post` is `false` on every session tool here but step 12: the
report is the one thing posted besides the checklist's own comment, and
`review_summary` posts once, editing the comment an earlier run left.

## The report in this flow

Write it as the skill's **4. The report** says, with these differences:

- **The result** there is step 10's answer, and `result.report` is step 10's. If
  step 10 did not answer, write *No verdict:* and why, and write neither headline
  yourself.
- In place of the *Steps:* line, under the Results table, one line says what this
  run paid for: *Ran now: … · Reused from earlier runs on this change: …* (or
  *Everything was reused — nothing ran again* when every step was), from each
  step's `cached: true` (`reused: true` from the checklist). Risk is re-read each
  time: it runs no AI once the slop score and the checklist are reused, and its
  bug history moves with the day.
- A step that failed, refused or timed out gets one line under the Results
  table saying which and why (`unavailable`, `degraded`, `context_refresh.reason`
  as given). Its row already says *not run*.
- `unmeasured` on the slop or risk result: say the score covers only what could
  be measured. **Name no reviewer from the risk result**; reviewers come from
  step 11 alone.
- **Suggested reviewers**, on a pull request, in place of the pull-request guide's lines:
  - Step 11 ran: the people in `recommended` — step 10's `reviewers`
    of them, in order — as `name` (`login`) — `role`, taken from `candidates`, never
    @-mentioned (a mention notifies them). When fewer were found than asked for,
    say how many were. Add
    one line: *suggested by this run, which requests no review;
    `/cloudaeye:assign-reviewer #<n>` asks for them when you want it.* When step
    12's `summary` says a review is already requested on GitHub, say who was asked
    instead of that line: this run cannot see GitHub's requests, and the
    pull-request comment names them. Then,
    right under it in the Summary, a small collapsible
    `<details><summary>How they were suggested (/cloudaeye:assign-reviewer)</summary>`
    holding step 11's `card` verbatim in a ```text fence: who, why, their review
    queue and the review focus. It is the only place the card is printed.
  - Step 11 failed: *none could be suggested* and its `error`.
- **Posted**, on a pull request: from step 12's `posted`, worded as the
  pull-request guide says. When step 12 never ran — the review failed, or a job
  was still pending at its deadline — say so in this line: *Not posted on the
  pull request: the run did not finish*, and why.
