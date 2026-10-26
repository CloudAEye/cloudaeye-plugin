---
name: assign-reviewer
description: Suggest who should review an open pull request, say why, show their review queue, and suggest what they should check — from code ownership (OWNERS.md) at minimum, and from whoever wrote the lines it changes, reviewed these files before or fixed bugs in them, balanced against each person's queue. Takes a note in your own words after the PR number ("hardik is away", "urgent, nobody busy"). When the repository has no OWNERS.md yet, it creates ownership at the root from git history first, in your working tree. It only suggests; it requests a review on GitHub only when you ask it to.
when_to_use: Use when the user asks who should review a pull request, wants a reviewer suggested or assigned, or asks to request a review. Not for whether a pull request is risky (that is /cloudaeye:risk-score).
argument-hint: "<PR number like #412> [a note: 'hardik is away', 'urgent, nobody busy']"
allowed-tools: ["mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__assign_reviewer", "mcp__cloudaeye__assign_reviewer", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
---

## Direct Result

`assign_reviewer` answers directly, both the recommendation and the request. Do
not poll for it or expect a job ID. It reads the risk score, AI slop and review
that already ran on this commit, so if a `/cloudaeye:risk-score` or review job
on this pull request is still queued or running, poll that job's existing ID
until it completes before calling; never start one to fill a gap.

## Steps

### Repository initialization gate

Before calling the tool, run the bundled preflight helper and call the
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
authoritative `repo`. Do not recompute it from local Git.

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

Do not call the tool until this gate reports `ready` or `initialized`.

### Pull requests only

`/cloudaeye:assign-reviewer 412` or `/cloudaeye:assign-reviewer #412`. With no
pull-request number, ask for one: who should review is a question about an open
pull request on GitHub.

**Anything after the number is the user's note about who to ask**, such as
`/cloudaeye:assign-reviewer #412 hardik is away, suggest someone else` or
`/cloudaeye:assign-reviewer #412 this is urgent, nobody busy`. Keep it as `NOTE`,
word for word, and pass it as `note` on every recommend call. Do not interpret it
yourself: the ranking applies it, leaves out whoever it rules out and names them on
the card, and puts someone with room in their queue first when it asks for speed.

1. **Recommend.** Call `assign_reviewer` with `repo=INIT.repo_full`,
   `pr_number` (the digits, any `#` stripped), `require_owners=true`, and
   `note=NOTE` when there is one. This call writes nothing anywhere.
   - `status: error` — report `error` and stop. An ineligible pull request
     (closed, from a fork, over 50 files, not into the integrated branch) is an
     answer, not something to work around.
   - `status: owners_missing` — the target branch has no `OWNERS.md`. Go to
     **Ownership first** below, then come back to step 2.
   - `status: ok` — go to step 2.

   **Ownership first** (only on `owners_missing`). Ownership lives in the
   repository, so what one person measures reaches everyone once it is merged.
   Until then the files in this working tree stand in for it.

   a. If the repository root in this working tree already has an `OWNERS.md`
      (an earlier run, not merged yet), use it: skip to c.

   b. Otherwise say one line — *`<target_branch>` has no OWNERS.md, so I'm
      creating ownership at the repository root from git history first. This
      runs on your machine and can take a few minutes.* — and run:

```bash
for c in python python3 py; do command -v "$c" >/dev/null 2>&1 && "$c" -c "" 2>/dev/null && { PY=$c; break; }; done
[ -n "$PY" ] || { echo "cloudaeye_error=python_not_found"; exit 1; }
"$PY" "${CLAUDE_PLUGIN_ROOT}/scripts/create_owners.py"
```

      It writes the root's `OWNERS.md`, and one in each folder down to three
      levels whose people differ. Report the files it wrote and their lead
      contributors in a short table. If `needs_a_handle` is not empty, name
      those people in one line and say `/cloudaeye:create-owners` asks for their
      GitHub usernames; do not ask now. On `"status": "error"`, say so and use
      `OWNERS = {}` in c, which gets a recommendation from git blame and
      GitHub's suggestions without ownership.

   c. Collect the files and ask again:

```bash
for c in python python3 py; do command -v "$c" >/dev/null 2>&1 && "$c" -c "" 2>/dev/null && { PY=$c; break; }; done
"$PY" "${CLAUDE_PLUGIN_ROOT}/scripts/create_owners.py" --collect
```

      Keep its `owners` object, exactly as printed, as `OWNERS`. Call
      `assign_reviewer` with `repo`, `pr_number`, `owners=OWNERS` (no
      `require_owners`) and `note=NOTE` when there is one, and handle the
      answer as in step 1. Pass the same `OWNERS` again in step 4.

2. **Print `card` verbatim.** It is rendered server-side, and three blocks lead:
   *Recommended reviewer* (name and role), *Why* (the model's reason first, then
   measured facts, their track record on these files when they have one, and
   their review queue) and *Suggested review focus*. Then the others worth
   considering, who was left out and why (the user's note included), and what
   the suggestion was based on. Do not reorder, shorten or reword it, and do not
   add people or reasons of your own.

   | field | what to do with it |
   |---|---|
   | `candidates` | Ranked people (`rank`, `login`, `name`, `reason`). Use it to turn "the first two" or "Ravi" into logins in step 4. Never add anyone who is not in it. |
   | `ranking.by` | `model` or `evidence`. With `evidence`, say in one line that the list is in evidence order, and why (`ranking.model_failed`). |
   | `ranking.avoided` | Who the note left out, and why. Already on the card under *Left out*. |
   | `ranking.note_unread` | The note could not be applied (no model answered). Say so in one line; the list is the evidence order. |
   | `needs_lead` | Why a lead should look, when the risk score, AI slop or CloudAEye's review said so. |
   | `signals.missing` | What was not measured, with the command that would measure it. Not measured is not low risk: say so if the user leans on it. |
   | `notes` | What could not be read (a tracker, a history). Gaps, never clean results. |
   | `problems` | Lines to fix in the OWNERS.md files. Mention them once. |
   | `draft` | A draft pull request: say reviews can be requested once it is ready. |

3. **End there.** Close with the link `[<repo>#<pr_number>](<pr_url>)`. When
   **Ownership first** ran, add one line: the `OWNERS.md` files are in the
   working tree, not committed; commit them through a pull request, and once
   merged every recommendation reads them from the repository. Never commit them
   yourself.

   **Do not ask who to ask.** The card is a suggestion. The developer may take
   it to the pull request themselves, or come back with a request.

   If the user answers about *who* rather than asking for a request — "not Ravi
   either", "someone in Platform", "it's urgent" — that is a new note: call step 1
   again with the earlier note and the new words together, and print the new card.

4. **Request, only when asked.** Requesting a review notifies people on GitHub,
   so do it only when the user explicitly asks — "ask Ravi", "request reviews
   from 1 and 2" — and only for people on the card. Never choose for them. If
   they name someone who is not a candidate, say so and stop. Call
   `assign_reviewer` with `repo`, `pr_number`, `apply=true`, `reviewers` = the
   exact logins (no `@`), and `expected_head=head_sha`, `expected_base=base_sha`
   from the recommendation, plus `owners=OWNERS` when **Ownership first** ran.
   Then read `assignment.status`:

   - `ok` — say who was asked; name anyone in `already_requested` or
     `already_reviewed` separately.
   - `failed` — report `error`; nobody new was asked.
   - `uncertain` — the request may or may not have reached GitHub. Say so, ask
     the user to check the pull request, and **do not retry**.

   If the outer `status` is `error` (the pull request moved since the
   recommendation, someone cannot review there, the CloudAEye GitHub App is not
   installed), report it and offer a fresh recommendation; never retry with
   other names.

## Notes

- The recommendation runs nothing: the risk score, AI slop and CloudAEye's review
  are read where they already ran on this commit. Do not run them yourself to
  fill a gap; the card names the command for each.
- Ownership comes from `OWNERS.md` files on the target branch. When the branch
  has none, the files in this working tree are used, and the card says they
  are not merged yet. The branch's always win: once any `OWNERS.md` is merged,
  local copies are ignored.
- Create ownership only on `owners_missing`, never because this working tree
  lacks a file: the branch may have them already.
- If `assign_reviewer` is unavailable (MCP not connected), warn and stop — **do
  not pick a reviewer yourself from `git log` or `git blame`**.
