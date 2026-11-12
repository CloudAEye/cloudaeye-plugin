---
name: explain
description: Explain a Jira or GitHub issue against the code it actually touches — the components involved, how they work today, and the related patterns and configuration around them. CloudAEye reads the repository's graph and vector store, which is why this answers things the issue text alone cannot.
when_to_use: Use when the user asks what an issue is about, what it would take to fix it, or which code it touches — before picking up a ticket, or when triaging one someone else filed. Takes a Jira key, a GitHub issue number, or an issue URL.
argument-hint: "jira <KEY|id> | github <issue#> | <issue URL>"
allowed-tools: ["Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__explain", "mcp__cloudaeye__explain", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
---

## Queued Result

Submit the analysis once. An answer without `job_id` is the response itself
(report `status: error` and stop). With a `job_id`, call
`mcp__plugin_cloudaeye_cloudaeye__get_job_result(job_id, wait_seconds=110, since=<last progress_id>)`
again and again, with no pause, while `status` is `queued`, `running` or
`retrying`. The server keeps each call open while the job runs.

- Right before submitting, print:
  `⏳ CloudAEye is reading the issue. This can take a few minutes; progress shows below.`
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

## What this is

CloudAEye reads the issue, picks the repository most relevant to it, and runs a
codebase query over that repository's graph and vector store: which components
the issue touches, how they work today, similar patterns elsewhere, and the
configuration and dependencies around them.

It answers **about an issue**, not about your working tree. It runs no review,
finds no bugs, and never edits code. For the pending diff use `/cloudaeye:ask`;
for "does my change satisfy this ticket" use `/cloudaeye:check-task`.

## The answer comes back here

Unlike `/cloudaeye:check`, `/cloudaeye:add-docs` and `/cloudaeye:add-tests`,
this one does not send the user somewhere else to read the result. The analysis
is in the `context` field. Print it.

One side effect to mention, not to build the report around: for a **Jira** or
**GitLab** issue CloudAEye also posts the analysis as a comment on the issue
itself, so a public comment appears on someone's ticket. `posted_to` says so
when it happened. For a GitHub issue nothing is posted and the field is absent.

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
- Anything else (`branch_required`, `setup_required`, an error): run
  `sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide connect-repository` and follow it.

Any `cloudaeye_error=…` line from a command: report it and stop.

Do not go on until this gate reports `ready` or `initialized`.

1. Read the issue reference from the argument.

   - `jira <KEY-or-id>` — pass `issue` as the key or id, `source` as `jira`.
   - `github <number>` — pass `issue` as the number, `source` as `github`.
   - A bare URL, or a bare Jira key like `PROJ-123` — pass it as `issue` and
     leave `source` empty. The server works it out.
   - **A bare number with no word in front is ambiguous** — Jira takes a numeric
     id too. Ask which tracker rather than assuming; the server will refuse it
     anyway, and asking is the faster path.

   If the user gave nothing, ask which issue. Do not guess from the branch name
   or from anything in the working tree.

2. Call `mcp__plugin_cloudaeye_cloudaeye__explain` with:
   - `issue`: the reference from step 1
   - `repo`: `INIT.repo_full`
   - `source`: `jira` or `github`, only when step 1 established it

   Submit once. Poll the returned MCP job ID via **Queued Result**; never
   call `explain` again to check progress.

   `repo` is what a bare issue number is resolved against. A Jira key does not
   need it — CloudAEye picks the relevant repository itself, and the response
   says which one it picked, which may not be the one you are standing in.

   If the tool is unavailable or the call fails outright, tell the user to
   authenticate CloudAEye through `/mcp` and stop.

3. Handle the `status` field before reading anything else.

   | `status` | what to do |
   |---|---|
   | `ok` | Report it — step 4. |
   | `pending` | Report the incomplete outcome and stop. Retain the MCP job ID if provided; do not invent one or re-submit `explain`. Normal queued waiting uses outer `queued`, `running`, or `retrying` status. |
   | `error` with a `note` about not retrying | A previous attempt failed and CloudAEye will not retry it on its own. Print the `error` and the `note` as written — a re-run returns the same failure, so do not offer one. |
   | `error` with `setup_required` | The repository is not integrated. Report the guidance and stop. |
   | `error` otherwise | Report the `error` field as written and stop. |

4. Report the result.

   - **`summary`**, as the server wrote it — it names the issue and the
     repository CloudAEye chose.
   - **`context`, in full, as markdown.** This is the answer and it is what the
     user asked for. Do not summarise it away, do not reorder it into your own
     headings, and do not extend it with your own reading of the code — it rests
     on a repository graph and vector store you do not have, and a sentence of
     yours mixed into it is indistinguishable from one of CloudAEye's.
   - **`repository`**, if it is not the repository the user is in. Say so
     plainly; an analysis of a different repository is still useful, but the user
     has to know that is what they are reading.
   - **`posted_to`**, when present — one line saying CloudAEye also left this as
     a comment on the issue, linked with `issue_url` when there is one. One line;
     the answer is above it.
   - **`reused: true`** — the analysis was generated earlier and CloudAEye does
     not re-explain an issue. **Always say this.** If the code has moved since,
     the analysis describes the older code, and nothing else in the output says
     so.

5. Stop there. If the user wants the issue implemented, that is ordinary work
   you do yourself — this command is context, not a plan.

## Notes

- **It never edits code, and never posts on a pull request.**
- **One analysis per issue.** Re-running is free of new charges but also free of
  new information; say that rather than running it again to "refresh".
- Jira works only if the tenant has the CloudAEye Jira app installed — that is
  what lets CloudAEye read the issue and comment on it. If a Jira reference comes
  back with an error naming the integration, that is the fix, not a retry.
- If `explain` is unavailable (MCP not connected), warn the user and skip.
