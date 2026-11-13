# An ultrareview of a pull request (only when the user gave a PR number)

The server fetches the pull request's diff from GitHub itself: nothing is uploaded. Follow the
skill's steps with what is below; the step numbers are the skill's own.

## Before step 1

In pull-request mode, say once under the tree: *the report is posted on the
pull request as one comment, as the other commands post their cards, and
edited in place when you run this again; the PR checklist keeps its own
comment, as `/cloudaeye:check` always does.*

In the tree, **PR checklist** runs, **Task check** is *skipped: uncommitted changes only*, and
**Human review** runs only if a human review is required.

## Step 1

The command is `cae start --pr`, with no other flag. Call `start_session` with every field of its
first line, unchanged, **and `pr_number`** (the digits, `#` stripped), and skip the upload. On `status: error`,
print the `error` as written and stop: it is the eligibility refusal (closed, wrong base branch,
fork, over 50 files), and each names a different thing to do. Never review the working tree
instead. **`demo: true` beside the `error` is not a refusal:** it is the report CloudAEye already posted on a
public demo repository's pull request. Print the `error` exactly as written and nothing else: no line
about a refusal, the session, checks that did not run or what was posted. Its last line, the link to
the comment, is where the run ends. On success, say which pull request this is (number, title, head SHA) and whether it is a
draft. Then read the settings as the target branch has them, so a pull request cannot change its
own: `cae pr-settings '<SESSION as JSON>' --review --guide ultrareview-settings`.

The same change as last time is `SESSION.diff_unchanged`. A new change's intent is the pull
request's own title and description; say in one line that it is the author's stated purpose.

## Steps 1, 4, 11 and 12

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

4. **Collect the checklist** (pull-request mode, when step 1 returned a
   `review_id`). Call `check_pr` with `repo`, `pr_number`, that `review_id`
   and `detail: true`. On `pending`, call again with the same `review_id`, at most
   three calls in all; if it is still pending, keep the `review_id` for the
   Check section and say risk may measure coverage on its own. Collecting it is
   what posts it, and risk reads its unit-test coverage from that comment.

In step 5 (change risk) pass no `author`: the author is the pull request's, and the checklist
supplies the unit-test coverage.

11. **Suggested reviewers — only when a human review is required.** When step
    10's `verdict` is `review` **and** this is a pull request **and** step 10 did
    not return `assign_reviewers: false` (your settings turned assigning off), call
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
    `policy` and `author` as step 10. The
    comment's suggested reviewers, and their card collapsed under them, come
    from step 11's call at this commit. Do this whatever the verdict,
    even when `summary` is empty or a step after the review failed — the
    comment says what did and did not run. It answers from step 10's stored
    summary without calling the model again, posts the whole report as one
    comment — or edits the one an earlier run posted — and returns `posted`.
    Never ask before posting: the PR number is the request. Never post on
    uncommitted changes or a path.

## In the report

Under **Suggested reviewers**:

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

**Posted.** In pull-request mode, one line under *What to do next* from step
12's `posted`: `ok` → *Posted on the pull request:* the link (`url`), saying
*updated in place* when `edited` is true and *unchanged* when `unchanged` is;
`failed` or `unavailable` → *Not posted on the pull request:* and its `note`;
`unknown` → that delivery could not be confirmed and it will not be retried
automatically — check the pull request before running again. When step 12
never ran — the review failed, or a job was still pending at its deadline —
say so in this line: *Not posted on the pull request: the run did not finish*,
and why. Never leave a pull-request run without this line.

After the report line, end with the link `[<repo>#<pr_number>](<pr_url>)`, where the report now sits.
