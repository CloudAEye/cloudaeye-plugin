---
name: assign-reviewer
description: Recommend who should review an open pull request, say why, and suggest what they should check — from code ownership (OWNERS.md) at minimum, and from whoever wrote the lines it changes, reviewed these files before or fixed bugs in them, balanced against each person's review queue. Requests the review on GitHub only after you name the people.
when_to_use: Use when the user asks who should review a pull request, wants a reviewer suggested or assigned, or asks to request a review. Not for whether a pull request is risky (that is /cloudaeye:risk-score).
argument-hint: "<PR number like #412>"
allowed-tools: ["mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__assign_reviewer", "mcp__cloudaeye__assign_reviewer"]
---

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

1. **Recommend.** Call `assign_reviewer` with `repo=INIT.repo_full` and
   `pr_number` (the digits, any `#` stripped). This call writes nothing anywhere.
   If it returns `status: error`, report `error` and stop — an ineligible pull
   request (closed, from a fork, over 50 files, not into the integrated branch)
   is an answer, not something to work around.

2. **Print `card` verbatim.** It is rendered server-side: the recommended
   reviewer, what they are to this code and their queue, why (the first line is
   the model's reason, every other line a measured fact), the suggested review
   focus, the others worth considering, who was left out and why, and what was
   not measured. Do not reorder, shorten or reword it, and do not add people or
   reasons of your own.

   | field | what to do with it |
   |---|---|
   | `candidates` | Ranked people (`rank`, `login`, `name`, `reason`). Use it to turn "the first two" or "1 and 3" into logins. Never add anyone who is not in it. |
   | `ranking.by` | `model` or `evidence`. With `evidence`, say in one line that the list is in evidence order, and why (`ranking.model_failed`). |
   | `needs_lead` | Why a lead should look, when the risk score, AI slop or CloudAEye's review said so. |
   | `signals.missing` | What was not measured, with the command that would measure it. Not measured is not low risk: say so if the user leans on it. |
   | `notes` | What could not be read (a tracker, a history). Gaps, never clean results. |
   | `problems` | Lines to fix in the OWNERS.md files. Mention them once. |
   | `draft` | A draft pull request: say reviews can be requested once it is ready, and stop. |

3. **Ask who to ask, and wait.** The card ends by asking. Requesting a review
   notifies people on GitHub, so it happens only when the user names them —
   by login, by name, or by rank number from the card. Never choose for them,
   and never add someone the card does not list. If they name someone who is
   not a candidate, say so and ask again.

4. **Request.** Call `assign_reviewer` again with `repo`, `pr_number`,
   `apply=true`, `reviewers` = the exact logins (no `@`), and
   `expected_head=head_sha`, `expected_base=base_sha` from step 1. Then read
   `assignment.status`:

   - `ok` — say who was asked; name anyone in `already_requested` or
     `already_reviewed` separately.
   - `failed` — report `error`; nobody new was asked.
   - `uncertain` — the request may or may not have reached GitHub. Say so, ask
     the user to check the pull request, and **do not retry**.

   If the outer `status` is `error` (the pull request moved since step 1,
   someone cannot review there, the CloudAEye GitHub App is not installed),
   report it and offer a fresh recommendation; never retry with other names.

5. End with the link: `[<repo>#<pr_number>](<pr_url>)`.

## Notes

- The recommendation runs nothing: the risk score, AI slop and CloudAEye's review
  are read where they already ran on this commit. Do not run them yourself to
  fill a gap; the card names the command for each.
- Ownership comes from `OWNERS.md` files on the target branch
  (`/cloudaeye:create-owners` writes them). Without any, the recommendation
  still works from git history and GitHub's own suggestions.
- If `assign_reviewer` is unavailable (MCP not connected), warn and stop — **do
  not pick a reviewer yourself from `git log` or `git blame`**.
