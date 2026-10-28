---
name: risk-score
description: Assess the change risk of an open pull request, or of your change before you push it — who wrote it, what it touches, and what those files and that author have been through over the last few weeks (bugs, rework, ownership, the author's pull requests, AI slop, test coverage) — and say whether it needs a human reviewer and why. Reports a risk score out of 100 with its band (low / medium / high), this PR's AI slop score, the bugs and rework in the files it changes beside the repository's rates, a verdict and the next step, what needs attention, the author with only the trends that got worse, and each changed file with bugs as a code area (stability, regression rate, rework, recent issues); it names no reviewer, never edits code and finds no bugs in the change itself.
when_to_use: Use when the user asks how risky a pull request is, whether it can be merged without a careful review, or for a change-risk card. Also before a commit, on the working tree, to see how risky a change is before opening a pull request. Not for who should review it. The history is the repository's, read on GitHub.
argument-hint: "[#PR [days]] | [--days N]  (no PR number: your working tree)"
allowed-tools: ["mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__start_session", "mcp__cloudaeye__start_session", "mcp__plugin_cloudaeye_cloudaeye__change_risk", "mcp__cloudaeye__change_risk", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
---

## Queued Result

Submit analysis once. A direct response without `job_id` uses the original
output rules below; report `status: error` and stop. An active response
(`queued`, `running`, `retrying`) without a non-empty `job_id` is malformed.

For a queued response, keep its `job_id` and poll
`mcp__plugin_cloudaeye_cloudaeye__get_job_result(job_id)` every 30 seconds using
the submitting OAuth account while status is `queued`, `running`, or `retrying`.
Stop after 60 polls or 30 minutes from submission, whichever comes first;
check the deadline before each call. On timeout or unavailable polling,
report the limitation and retain the ID for later. Never re-submit to check
progress or start replacement work automatically.

On `completed`, require a `result` dictionary and use it as **the response**
below, preserving the tool's original fields. Completion is not a clean
verdict: report an inner `status: error` as a refusal. Stop on outer `failed`
or `error`; report missing/expired results, never treat them as empty or clean.
Finish the job before dependent actions, edits, or another review/fix/upload
on the same session; a pending job does not cover new code.

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
   gh api user --jq .login 2>/dev/null || true
   git config user.email 2>/dev/null || true
   ```

   `AUTHOR` is the first that gives a login: the `gh` output, or the name in an
   email of the form `<id>+<name>@users.noreply.github.com`. Otherwise leave it
   empty: the server finds it from your sign-in when it can, and when it cannot,
   the author rows are reported as not measured.

   Then collect the branch and HEAD, call `start_session` with
   `INIT.repo_full`, `branch` and `head` (no `pr_number`), validate what it
   returns, and upload the diff — exactly as `/cloudaeye:review` does on a
   working tree: `session_id` hex digits and dashes, `upload_token` 64 hex
   characters, `upload_url` HTTPS or localhost HTTP, `target_branch` matching
   `[A-Za-z0-9._/-]+` or empty. One Bash call; the token goes only into a
   private temporary curl config.

   ```bash
   cd "$(git rev-parse --show-toplevel)" || exit 1
   mkdir -p .cloudaeye/session && printf '*\n' > .cloudaeye/.gitignore
   CE_SESSION='<session_id>'
   CE_UPLOAD_URL='<upload_url>'
   CE_UPLOAD_TOKEN='<upload_token>'
   TARGET='<validated target_branch or empty>'
   case "$CE_SESSION" in ''|*[!0-9A-Fa-f-]*) echo "cloudaeye_error=bad_session"; exit 1;; esac
   case "$CE_UPLOAD_TOKEN" in *[!0-9A-Fa-f]*|'') echo "cloudaeye_error=bad_upload_token"; exit 1;; esac
   [ "${#CE_UPLOAD_TOKEN}" = 64 ] || { echo "cloudaeye_error=bad_upload_token"; exit 1; }
   case "$CE_UPLOAD_URL" in https://*|http://localhost/*|http://localhost:*|http://127.0.0.1/*|http://127.0.0.1:*) ;; *) echo "cloudaeye_error=insecure_url"; exit 1;; esac
   CE_TMP=$(mktemp -d 2>/dev/null) || CE_TMP="${TMPDIR:-${TMP:-/tmp}}/cloudaeye-$$"
   mkdir -p "$CE_TMP" || { echo "cloudaeye_error=bad_config"; exit 1; }
   trap 'rm -rf "$CE_TMP"' EXIT INT TERM
   printf 'header = "X-Upload-Token: %s"\n' "$CE_UPLOAD_TOKEN" > "$CE_TMP/curl.cfg"
   chmod 600 "$CE_TMP/curl.cfg" 2>/dev/null || true
   case "$TARGET" in ''|-*|*[!A-Za-z0-9._/-]*) TARGET="";; esac
   HEAD_SHA=$(git rev-parse HEAD); BASE=""; SRC=fork_point
   if [ -n "$TARGET" ]; then
     git rev-parse --verify -q "origin/$TARGET" >/dev/null 2>&1 || \
       GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=never GIT_ASKPASS=echo \
       git -c credential.helper= fetch -q origin "$TARGET" 2>/dev/null
     BASE=$(git merge-base "origin/$TARGET" HEAD 2>/dev/null)
   fi
   [ -n "$BASE" ] || { BASE=$HEAD_SHA; SRC=head; }
   git add --intent-to-add . >/dev/null 2>&1
   git diff "$BASE" > .cloudaeye/session/session.diff
   UP=$(curl -s -m 120 -K "$CE_TMP/curl.cfg" -o /dev/null -w '%{http_code}' \
     -F "file=@.cloudaeye/session/session.diff" -F "base_sha=$BASE" "$CE_UPLOAD_URL")
   echo "session_id=$CE_SESSION base_source=$SRC diff_bytes=$(wc -c < .cloudaeye/session/session.diff) upload_http=$UP"
   ```

   `cloudaeye_error=…` or `upload_http` not `200`: report it and stop.
   `diff_bytes=0`: nothing to assess — say so and stop. `base_source=head`: the
   diff holds only uncommitted edits, so say the history was compared against
   your local HEAD.

#### Both

2. Call `change_risk` with `session_id`, `days` when the user gave one, and on
   the working tree `author: AUTHOR` (omit it when empty). Follow **Queued
   Result** above, then read `result`. One argument writes, and it needs a
   decision:

   - `post` (**pull request only**): **writes the card on the pull request**,
     where reviewers see it (editing CloudAEye's earlier risk card there rather
     than adding a second). Pass `true` only after saying in one line —
     *CloudAEye will post the risk card on pull request #<n>* — and getting a
     clear yes. Never pass it on the working tree: there is nothing to post on,
     and the server refuses it.

   The assessment never writes on bug issues or Jira tickets. Where each bug is
   in the code (its files and who wrote them) is mapped in the background by
   CloudAEye when the bug is filed, fixed or reopened, and the assessment only
   reads those notes.

   What is already measured at the pull request's commit is reused. What is
   missing is filled in: the AI slop review runs when there is none, and when
   the repository's PR checklist enables unit-test coverage and none is on the
   pull request, the checklist runs for it. Neither is posted; the card's
   footnote says what was filled in.

3. Print `result.card` **verbatim**. It already carries the next step, so do
   not repeat it. On a pull request with no post requested (no `posted`), add
   one line: *reply "post" to put it on #<n>*. Otherwise report the delivery
   status and note; `unknown` does not establish whether the card was posted.
   Never re-enqueue to retry a post. End with the link. On the working tree
   (`subject: "change"`) there is no link and no post line: say once that the
   card is about the change before it is pushed, and that running it again on
   the pull request adds test coverage and can post the card. Then stop.

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
