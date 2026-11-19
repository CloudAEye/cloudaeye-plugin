---
name: risk-score
description: Assess the change risk of an open pull request, or of your change before you push it — who wrote it, what it touches, and what those files and that author have been through over the last few weeks (bugs, rework, ownership, the author's pull requests, AI slop, test coverage) — and say whether it needs a human reviewer and why. Reports a risk score out of 100 with its band (low / medium / high), this PR's AI slop score, the bugs and rework in the files it changes beside the repository's rates, a verdict and the next step, what needs attention, the author with only the trends that got worse, and each changed file with bugs as a code area (stability, regression rate, rework, recent issues); it names no reviewer, never edits code and finds no bugs in the change itself.
when_to_use: Use when the user asks how risky a pull request is, whether it can be merged without a careful review, or for a change-risk card. Also before a commit, on the working tree, to see how risky a change is before opening a pull request. Not for who should review it. The history is the repository's, read on GitHub.
argument-hint: "[#PR [days]] | [--days N]  (no PR number: your working tree)"
allowed-tools: Read, Grep, Glob, LS
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

1. Find the repository with this one read-only command (This skill runs no script, so Claude
   Code asks before the first run of a command it has not been allowed):

   ```bash
   git rev-parse --show-toplevel HEAD --abbrev-ref HEAD && git remote get-url origin
   ```

   It prints four lines: `TOP` (the repository's folder), `HEAD`, `BRANCH` and `ORIGIN`. An error
   (not a Git repository, no `origin` remote): stop and say CloudAEye needs a Git repository with
   a GitHub, GitLab or Bitbucket remote. Call `start_session` with `repo_url` = `ORIGIN`,
   `provider` (`github` for github.com, `bitbucket` for bitbucket.org, `gitlab` for a GitLab
   host), `branch` = `BRANCH` and `head` = `HEAD`, **and `pr_number`** (the digits, any `#` stripped), and keep the answer as `SESSION`.
   The server fetches the pull request and its diff itself; there is nothing to
   upload. `SESSION.gate` is `repository`: the repository is not connected yet;
   read `${CLAUDE_PLUGIN_ROOT}/resources/skills/connect-repository.md` and follow it. Any other
   `status: error`: report the `error` and stop — an ineligible pull request
   (closed, from a fork, over 50 files, not into the integrated branch) is an
   answer, not something to work around.

#### Working tree

1. Find the repository with this one read-only command (This skill runs no script, so Claude
   Code asks before the first run of a command it has not been allowed):

   ```bash
   git rev-parse --show-toplevel HEAD --abbrev-ref HEAD && git remote get-url origin
   ```

   It prints four lines: `TOP` (the repository's folder), `HEAD`, `BRANCH` and `ORIGIN`. An error
   (not a Git repository, no `origin` remote): stop and say CloudAEye needs a Git repository with
   a GitHub, GitLab or Bitbucket remote. Call `start_session` with `repo_url` = `ORIGIN`,
   `provider` (`github` for github.com, `bitbucket` for bitbucket.org, `gitlab` for a GitLab
   host), `branch` = `BRANCH` and `head` = `HEAD`, and keep the answer as `SESSION`.
   The author rows are about you: the server finds your GitHub account from your
   CloudAEye sign-in, and when it cannot, it reports the author rows as not measured.

   - `SESSION.gate` is `repository`: the repository is not connected yet. Read
     `${CLAUDE_PLUGIN_ROOT}/resources/skills/connect-repository.md` and follow it.
   - The tool is unavailable, or `status` is `error`: stop and tell the user to
     authenticate CloudAEye through `/mcp`.

   Upload the change with this one command, writing in `<TARGET>`
   (`SESSION.target_branch`), `<UPLOAD_URL>` and `<UPLOAD_TOKEN>` from `SESSION`. It writes
   only under `.cloudaeye/` (which ignores itself) and leaves your git index as it was. It runs in `TOP`: when that is not
   the folder Claude Code is working in, put `cd '<TOP>' && ` in front of it. When
   `SESSION.target_branch` is empty, or the command stops at a `git` error before the upload runs, read
   `${CLAUDE_PLUGIN_ROOT}/resources/skills/no-target-branch.md` instead.

   ```bash
   git -c credential.helper= fetch -q origin '<TARGET>' 2>/dev/null; mkdir -p .cloudaeye && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Upload-Token:%s"\n' '<UPLOAD_URL>' '<UPLOAD_TOKEN>' | tee .cloudaeye/upload.curl && git rev-parse --git-path index | xargs -I{} cp -p {} .cloudaeye/index && export GIT_INDEX_FILE=.cloudaeye/index && git add -N . && git diff --merge-base 'origin/<TARGET>' --output=.cloudaeye/session.diff -- . && git merge-base HEAD 'origin/<TARGET>' | curl -sS --fail-with-body -K .cloudaeye/upload.curl -F 'base_sha=<-' -F 'file=@.cloudaeye/session.diff'
   ```

   It prints the upload's settings file, then the server's answer as JSON. An upload error (`(22)`):
   report it and stop. `diff_files` is `0`: nothing to assess — say so and stop. Never
   print the upload token.

#### Both

2. Call `change_risk` with `session_id` and `days` when the user gave one. Follow **Queued
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
   with this one command:

   ```bash
   mkdir -p .cloudaeye/reports && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Report-Token:%s"\n' '<result.report.url>' '<result.report.token>' | tee .cloudaeye/report.curl && curl -sS --fail-with-body -K .cloudaeye/report.curl -o .cloudaeye/reports/risk-score.md && echo 'report_path=.cloudaeye/reports/risk-score.md'
   ```

   Then your final message is **`result.card` verbatim and whole**, as markdown and **never inside a code block** (Claude Code colours a code block with its own theme, which is unreadable on a light terminal), ending with
   `Full report: <report_path>`. It already carries the next step, so do not repeat it. There is
   no link and no post line: say once that the card is about the change before it
   is pushed, and that running it again on the pull request adds test coverage and
   posts the card. Then stop.

   The card is rendered server-side because what it may show is the feature:
   it opens with a summary table in ultrareview's words (Risk score, AI slop score, Bugs, Code churn — each beside the repository's rate — Recommendation, Next steps), then what needs attention, ranked, then the author, one marked
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
   | `subject` | `change` on the working tree: the card speaks of "this change", coverage is a stated gap, and the author is you. When the author rows say *the author's GitHub login is not known*, say CloudAEye could not match your sign-in to a GitHub account, and that linking GitHub to your CloudAEye account fixes it. |

## Notes

- **Quote the numbers the card prints, never others.** Do not compute, round
  or re-derive a score from the rows. State the score plainly: never call it
  uncalibrated, approximate or provisional.
- **The author rows are about the pull request, not a judgement of the
  person.** Report them as the facts they are — counts and links.
- **Name no reviewer.** The card says whether a human must review the change,
  never who. Do not suggest a person from its authors, file shares or blame,
  and do not @-mention anyone it names.
- Single-shot: one call, print the card, done.
- If `change_risk` is unavailable (MCP not connected), warn and skip — **do
  not assess the risk yourself from `git log`**. The card's value is that every
  number is measured the same way on every pull request.
