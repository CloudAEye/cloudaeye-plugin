---
name: risk-score
description: Assess the change risk of an open pull request — who wrote it, what it touches, and what those files and that author have been through over the last few weeks (bugs, rework, ownership, the author's pull requests, AI slop, test coverage) — and say whether it needs a human reviewer, why, and who to ask. Reports a risk score out of 100 with its band (low / medium / high), this PR's AI slop score, a verdict, what needs attention and the week-by-week evidence; it never edits code and finds no bugs in the change itself.
when_to_use: Use when the user asks how risky a pull request is, whether it can be merged without a careful review, who should review it, or for a change-risk card. Pull requests only — the history is the repository's, read on GitHub.
argument-hint: "<PR number like #412> [days, 7-90, default 21]"
allowed-tools: ["mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__start_session", "mcp__cloudaeye__start_session", "mcp__plugin_cloudaeye_cloudaeye__change_risk", "mcp__cloudaeye__change_risk", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
---

## Steps

### Repository initialization gate

Before creating a session, run the bundled preflight helper and call the
session-free initialization tool. This is required before every operational command.

```bash
   for c in python python3 py; do command -v "$c" >/dev/null 2>&1 && "$c" -c "" 2>/dev/null && { PY=$c; break; }; done
   [ -n "$PY" ] || { echo "cloudaeye_error=python_not_found"; exit 1; }
   META=$("$PY" "${CLAUDE_PLUGIN_ROOT}/scripts/repository_preflight.py") || { printf '%s\n' "$META"; exit 1; }
printf '%s\n' "$META"
```

Call `mcp__plugin_cloudaeye_cloudaeye__initialize_repository` with the detected
`provider`, `repo_url`, and an empty `monitor_branch`, and keep its response as
`INIT`. If it returns `branch_required`, ask `Branch to monitor [base_branch]:`;
Enter keeps the displayed base branch. Set `BRANCH` to that answer (or the
displayed base branch); if there is no base branch, require a non-empty answer.
Rerun the helper with `--branch "$BRANCH"`, set
`MONITOR_BRANCH` from that helper result, and call initialization again with
`monitor_branch=MONITOR_BRANCH`. Keep the same `MONITOR_BRANCH` for every retry.

If initialization returns `setup_required`, validate and open `integration_url`
below, then poll every 10 seconds for at most 30 attempts. Each poll must call
initialization with the original `provider` and `repo_url` and the same
`monitor_branch=MONITOR_BRANCH`; replace `INIT` with each response. Continue
only after `INIT.status` is `ready` or `initialized`; stop on errors, conflicts,
or timeout. Never treat `provider_connected` alone as success.

When `INIT.status` is `ready` or `initialized`, use `INIT.repo_full` as the
authoritative `repo` for `start_session`. Do not recompute it from local Git.

```bash
LINK='<integration_url from the tool>'
case "$LINK" in
  https://*|http://localhost/*|http://localhost:*|http://127.0.0.1/*|http://127.0.0.1:*) ;;
  *) echo "cloudaeye_error=insecure_integration_url"; exit 1 ;;
esac
if command -v open >/dev/null 2>&1; then open "$LINK"
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$LINK"
elif command -v powershell.exe >/dev/null 2>&1; then
  CE_LINK="$LINK" powershell.exe -NoProfile -Command 'Start-Process -LiteralPath $env:CE_LINK'
elif command -v cmd.exe >/dev/null 2>&1; then cmd.exe /c start "" "$LINK"
else printf 'quick_link=%s\n' "$LINK"
fi
```

Do not start a session until this gate reports `ready` or `initialized`.


### Pull requests only

`/cloudaeye:risk-score 412` or `/cloudaeye:risk-score #412`, optionally followed by
a window in days (`/cloudaeye:risk-score #412 30`). With no pull-request number, ask for one —
there is no working-tree mode: bugs, rework and the author's history are read
from the repository on GitHub, and a working tree has none of them.

1. Call `start_session` with `INIT.repo_full`, the current `branch` and `head`,
   **and `pr_number`** (the digits, any `#` stripped). The server fetches the
   pull request and its diff itself; there is nothing to upload. If it returns
   `status: error`, report the `error` and stop — an ineligible pull request
   (closed, from a fork, over 50 files, not into the integrated branch) is an
   answer, not something to work around.

2. Call `change_risk` with `session_id` and, when the user gave one, `days`.
   It queues; poll `get_job_result(job_id)` every 30 seconds until it is
   `completed`, then read `result`. One argument writes, and it needs a
   decision:

   - `post`: **writes the card on the pull request**, where reviewers see it
     (editing CloudAEye's earlier risk card there rather than adding a second).
     Pass `true` only after saying in one line — *CloudAEye will post the risk
     card on pull request #<n>* — and getting a clear yes.

   The assessment never writes on bug issues or Jira tickets. Where each bug is
   in the code (its files and who wrote them) is mapped in the background by
   CloudAEye when the bug is filed, fixed or reopened, and the assessment only
   reads those notes.

3. Print `result.card` **verbatim**. Then one line, `Next:` followed by
   `result.next_step` as given, and, when the card is not on the pull request
   yet (no `posted`, or `posted.status` other than `ok`), *reply "post" to put
   it on #<n>*. End with the link. Then stop.

   The card is rendered server-side because what it may show is the feature:
   it opens with the verdict (the score, this PR's AI slop, the recommendation
   and who to ask), then what needs attention, ranked, then the evidence week
   by week; every concern names a file, an issue or a pull request, and what
   could not be measured is listed rather than read as clean. Do not reorder it,
   round it, or summarise it into prose.

   | field | what to do with it |
   |---|---|
   | `verdict` | `review` — say *human review required* first; `approve` — *no extra review needed*. |
   | `score` | The risk score out of 100, as the card prints it. Never say how it is built (weights, points per row): the result does not carry them, on purpose. |
   | `band` | `low`, `medium` or `high`. **Empty means too little was measured to name one** — say that, never "low". |
   | `next_step` | The one action to suggest, chosen by rule. Say it as given; do not add others. |
   | `slop` | This PR's AI slop score (`score`, `band`) and whether it was reused or run for this card (`ran`: `reused` / `ran`). `measured: false` blocks automatic approval: say so. |
   | `unmeasured` | Each is a gap in the evidence, not a clean result. Mention them when the user asks whether the change is safe. |
   | `reviewers` | Who to ask and why. A name without `@` has no linked GitHub account. |
   | `reused` | CloudAEye's card on the pull request was already about this commit and window; nothing was recomputed. |
   | `census.bugs.unmapped` | Bugs in the window not yet mapped to the code. They are left out of the band — a gap, never a clean history. |
   | `posted.status` | `ok` means the card is on the pull request. Anything else means it is **not** — say so and why. Never write "posted" without reading this. |
   | `pr_url` | **End with a link** — `[<repo>#<pr_number>](<pr_url>)`. |

## Notes

- **Quote the numbers the card prints, never others.** Do not compute, round
  or re-derive a score from the rows. The score is not calibrated yet and the
  card's footnote says so: say it too if the user leans on the exact figure.
- **The author rows are about the pull request, not a judgement of the
  person.** Report them as the facts they are — counts and links.
- Single-shot: one call, print the card, done.
- If `change_risk` is unavailable (MCP not connected), warn and skip — **do
  not assess the risk yourself from `git log`**. The card's value is that every
  number is measured the same way on every pull request.
