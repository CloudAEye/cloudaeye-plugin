---
name: create-issue
description: File findings from a CloudAEye review as tracking issues — a Jira ticket or a GitHub issue, with an optional assignee. Takes the finding numbers the review printed. It creates real tickets; it never edits code.
when_to_use: Use after a CloudAEye review, when the user wants a finding tracked rather than fixed now — "raise a ticket for that", "file the second one to Jira", "create an issue for the auth bug". For fixing a finding instead, use /cloudaeye:implement.
argument-hint: "[2] jira Jane Doe   ·   [1,3] github octocat"
allowed-tools: ["mcp__plugin_cloudaeye_cloudaeye__create_issue", "mcp__cloudaeye__create_issue", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
---

## Direct Result

`create_issue` returns ticket results directly. Do not poll for ticket creation
or expect a job ID. Wait for any preceding review job to finish before calling.

## What this is

The other direction from `/cloudaeye:check-task`. That one reads a ticket and
asks whether the change satisfies it. This one takes a finding the review
already produced and opens a ticket for it.

It works on the findings of the **last review in this session** — whatever
`/cloudaeye:inspect`, `/cloudaeye:security` or `/cloudaeye:review` printed. That
means it works pre-commit, before any pull request exists, which is the case the
`@cloudaeye /create_issue` command on a PR cannot cover.

**This creates real tickets.** They land on a board, they can carry an
assignee, and somebody has to close them. Treat it like `/cloudaeye:add-docs`:
confirm before calling.

## Steps

1. **There must be a review in this session already.** If none has run, say so
   and offer to run one — do not run it silently, and never invent findings to
   file.

   If that review is still queued/running/retrying, poll its existing job ID
   until it completes and read its original numbered findings before continuing.
   Do not pass a `review_job_id`; the tool reads the session's saved report.
   Do not run another review or fix workflow concurrently on this session.

2. **Read which findings the user means, and do not guess.**

   The tool takes the numbers the review printed: `[2]`, `[1,3]`, `[2-4]`. It
   does **not** accept free text — if the user said "file the auth one",
   resolve it yourself against the numbered list you printed and pass the
   number. If you are not certain which they mean, ask. A wrong number files a
   ticket about the wrong defect and puts somebody's name on it.

   **There is no "all findings" form, deliberately.** If the user says "file
   them all", confirm the count first — "that is 6 tickets, go ahead?" — and
   then pass the explicit list.

3. **Read the provider and assignee from the argument.**

   | | provider | assignee |
   |---|---|---|
   | Jira | `jira` (default) | display name — `Jane Doe` |
   | GitHub | `github` | username — `octocat` |

   The assignee is optional. Do not invent one, and do not assume the user
   wants themselves assigned.

4. **Call `create_issue`** with `session_id`, `request` (the numbers),
   `provider`, `assignee`, and `note` — the note being what the user wants
   said about it ("let's fix this before the release"). It goes above the
   finding in the ticket description.

   Before submitting, show the exact findings, ticket count, tracker, and any
   assignee/note, then obtain explicit user approval. Call once and interpret
   the direct ticket outcomes below.

5. **Report what happened, per list in the response.**

   - **`filed`** — one line each: the finding, and the ticket key with its link
     where there is one. This is the whole point of the output; lead with it.
   - **`already_filed`** — that finding already has a ticket from this session
     and was **not** filed again. Say so plainly and name the existing ticket.
     It is not a failure and not something to retry.
   - **`failed`** — print the `error` as written. `no Jira integration` is
     configuration to fix, not an outage; `issues are disabled` is a GitHub
     repository setting. Neither is worth retrying as-is.
   - **Interrupted request / unconfirmed delivery** - an external write may have happened.
     Report the uncertainty; do not repeat the request automatically. Check
     the tracker first before any explicitly authorized new attempt.
   - **`assignee_dropped`** on a filed entry — the issue exists but that user
     could not be assigned on that repository. Say both halves; the ticket is
     real and it is unassigned.

6. **Never say the finding is fixed or closed.** Filing a ticket records it;
   only re-running the review can say the defect is gone. If the user wants it
   fixed now, that is `/cloudaeye:implement`.

## Notes

- **Do not automatically repeat ticket writes.** Confirmed prior tickets are
  matched by content, not review number, but an interrupted/unconfirmed write
  may still exist externally. Check the tracker before an explicitly approved
  retry; do not call create_issue again just to check delivery.
- **Jira works without a pull request**; so does GitHub, which files against the
  session's repository.
- **It never edits your working tree** and never opens a pull request.
- If the tool is unavailable (MCP not connected), warn the user and skip.
