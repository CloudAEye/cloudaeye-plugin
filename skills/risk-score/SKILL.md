---
name: risk-score
description: Assess the change risk of an open pull request, or of your change before you push it — who wrote it, what it touches, and what those files and that author have been through over the last few weeks (bugs, rework, ownership, the author's pull requests, AI slop, test coverage) — and say whether it needs a human reviewer and why. Reports a risk score out of 100 with its band (low / medium / high), this PR's AI slop score, the bugs and rework in the files it changes beside the repository's rates, a verdict and the next step, what needs attention, the author with only the trends that got worse, and each changed file with bugs as a code area (stability, regression rate, rework, recent issues); it names no reviewer, never edits code and finds no bugs in the change itself.
when_to_use: Use when the user asks how risky a pull request is, whether it can be merged without a careful review, or for a change-risk card. Also before a commit, on the working tree, to see how risky a change is before opening a pull request. Not for who should review it. The history is the repository's, read on GitHub.
argument-hint: "[#PR [days]] | [--days N]  (no PR number: your working tree)"
allowed-tools: ["Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__start_session", "mcp__cloudaeye__start_session", "mcp__plugin_cloudaeye_cloudaeye__change_risk", "mcp__cloudaeye__change_risk", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
---

## Queued Result

Submit the analysis once. An answer without `job_id` is the response itself
(report `status: error` and stop). With a `job_id`, call
`mcp__plugin_cloudaeye_cloudaeye__get_job_result(job_id, wait_seconds=110, since=<last progress_id>, report="risk-score")`
again and again, with no pause, while `status` is `queued`, `running` or
`retrying`. The server keeps each call open while the job runs.

- Right before submitting, print:
  `⏳ CloudAEye is assessing the risk of your change. This can take a few minutes; progress shows below.`
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


### Two ways in

| Argument | Mode |
|---|---|
| `#412`, or bare digits like `412`, optionally a window: `#412 30` | **Pull request** — PR 412 of this repository. |
| *none*, optionally `--days 30` | **Working tree** — your uncommitted and unpushed change, before you open a pull request. |

The window is 7–90 days, 21 by default. Digits mean a pull request; on the
working tree the window is given as `--days N`.

The history is the repository's either way — bugs, rework and ownership are
read from GitHub at the integrated branch, and the change's AI slop score runs
on the change itself. A working tree differs from a pull request in four ways,
and the card says so: the author is **you**, nothing from a pull request is
read, **unit-test coverage is not measured** (it comes from the PR checklist,
which needs a pull request), and **nothing can be posted**.

#### Pull request

1. Call `start_session` with `INIT.repo_full`, the current `branch` and `head`,
   **and `pr_number`** (the digits, any `#` stripped). The server fetches the
   pull request and its diff itself; there is nothing to upload. If it returns
   `status: error`, report the `error` and stop — an ineligible pull request
   (closed, from a fork, over 50 files, not into the integrated branch) is an
   answer, not something to work around.

#### Working tree

1. Find your GitHub username, so the author rows are about you:

   ```bash
   sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae login
   ```

   `AUTHOR` is what it prints after `author=`. Empty means leave it out: the
   server finds it from your sign-in when it can, and when it cannot, the
   author rows are reported as not measured.

   Then call `start_session` with `INIT.repo_full` and the `branch` and `head`
   the initialization gate printed (no `pr_number`), and upload the change:
   exactly this one command, alone in its Bash call, with `start_session`'s whole
   answer as JSON inside single quotes.

   ```bash
   sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae upload '<the start_session answer as JSON>'
   ```

   `cloudaeye_error=…` or `upload_http` not `200`: report it and stop.
   `diff_bytes=0`: nothing to assess — say so and stop. `base_source=head`: the
   diff holds only uncommitted edits, so say the history was compared against
   your local HEAD.

#### Both

2. Call `change_risk` with `session_id`, `days` when the user gave one, and on
   the working tree `author: AUTHOR` (omit it when empty). Follow **Queued
   Result** above, then read `result`. One argument writes:

   - `post`: on a **pull request**, always `true` — the card goes on the pull
     request, as every CloudAEye command posts on a pull request, editing
     CloudAEye's earlier risk card there rather than adding a second. Never pass
     it on the working tree: there is nothing to post on, and the server refuses
     it.

   The assessment never writes on bug issues or Jira tickets. Where each bug is
   in the code (its files and who wrote them) is mapped in the background by
   CloudAEye when the bug is filed, fixed or reopened, and the assessment only
   reads those notes.

   What is already measured at the pull request's commit is reused. What is
   missing is filled in: the AI slop review runs when there is none, and when
   the repository's PR checklist enables unit-test coverage and none is on the
   pull request, the checklist runs for it. Neither is posted; the card's
   footnote says what was filled in.

3. **On a pull request:** the card is on the pull request. Print a short summary —
   the risk score and band, the recommendation (`verdict`: `review` → *human review
   required*, `approve` → *no extra review needed*) and `next_step` — then *Posted
   on the pull request:* with `posted.url` (*updated in place* when `edited`), or
   the delivery `status` and `note` when it is not `ok`; `unknown` does not
   establish whether the card was posted. Never re-enqueue to retry a post. Offer
   to print the whole card here, then stop.

   **On the working tree** (`subject: "change"`): first save the fuller card, with its tables
   (exactly this one command, alone in its Bash call):

   ```bash
   sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae report risk-score '<result.report as JSON>'
   ```

   Then your final message is **`result.card` verbatim and whole**, ending with
   `Full report: <report_path>`. It already carries the next step, so do not repeat it. There is
   no link and no post line: say once that the card is about the change before it
   is pushed, and that running it again on the pull request adds test coverage and
   posts the card. Then stop.

   The card is rendered server-side because what it may show is the feature:
   it opens with a summary (the score, this PR's AI slop, the bugs and rework in
   the changed files beside the repository's rates, the recommendation and the
   next step), then what needs attention, ranked, then the author, one marked
   line a signal with only the trends that got worse and their pull requests in
   the window, then the code changes: its tests and a code area for each changed
   file with bugs (stability, bug trend, regression rate, rework, ownership,
   recent issues). Every concern
   names a file, an issue or a pull request, and what could not be measured is
   marked ⚪ with the reason rather than read as clean. Do not reorder it, round
   it, or summarise it into prose.

   | field | what to do with it |
   |---|---|
   | `verdict` | `review` — say *human review required* first; `approve` — *no extra review needed*. |
   | `score` | The risk score out of 100, as the card prints it. Never say how it is built (weights, points per row): the result does not carry them, on purpose. |
   | `band` | `low`, `medium` or `high`. **Empty means too little was measured to name one** — say that, never "low". |
   | `next_step` | The one action to suggest, chosen by rule, already on the card. If you mention it again, say it as given; do not add others. |
   | `slop` | This PR's AI slop score (`score`, `band`) and where it came from (`ran`: `ran` — reviewed for this card; `reused` — an earlier review or risk card at this commit, nothing paid twice). `measured: false` blocks automatic approval: say so. |
   | `unmeasured` | Each is a gap in the evidence, not a clean result. Mention them when the user asks whether the change is safe. |
   | `census.bugs.unmapped` | Bugs in the window not yet mapped to the code. They are left out of the score — a gap, never a clean history. |
   | `posted.status` | Only `ok` confirms the card is on the pull request. `unavailable` or `failed` means it is not; `unknown` means delivery was not confirmed and will not be repeated automatically. Say so and why. Never write "posted" without reading this. |
   | `pr_url` | **End with a link** — `[<repo>#<pr_number>](<pr_url>)`. Absent on the working tree: give no link and never construct one. |
   | `subject` | `change` on the working tree: the card speaks of "this change", coverage is a stated gap, and the author is you. When the author rows say *the author's GitHub login is not known*, suggest signing in to the GitHub CLI (`gh auth login`) so the next run can find it. |

## Notes

- **Quote the numbers the card prints, never others.** Do not compute, round
  or re-derive a score from the rows. The score is not calibrated yet and the
  card's footnote says so: say it too if the user leans on the exact figure.
- **The author rows are about the pull request, not a judgement of the
  person.** Report them as the facts they are — counts and links.
- **Name no reviewer.** The card says whether a human must review the change,
  never who. Do not suggest a person from its authors, file shares or blame,
  and do not @-mention anyone it names.
- Single-shot: one call, print the card, done.
- If `change_risk` is unavailable (MCP not connected), warn and skip — **do
  not assess the risk yourself from `git log`**. The card's value is that every
  number is measured the same way on every pull request.
