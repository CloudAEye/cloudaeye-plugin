---
name: implement
description: Plan a fix for findings a CloudAEye review already produced. You say which ones in your own words — "fix the 2nd point, and use a context manager" — and the server returns a fix plan grounded in the repository's code graph, including the call sites and tests the change affects. It plans; it never edits on its own.
when_to_use: Use after /cloudaeye:inspect, /cloudaeye:security or /cloudaeye:review has returned findings and the user wants help fixing some of them. Fixing a finding directly without this skill is also fine — this is for when the plan should account for the whole repository, not just the file being edited.
argument-hint: "[finding numbers like [1,3], or nothing for all of them]"
allowed-tools: ["Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__start_session", "mcp__cloudaeye__start_session", "mcp__plugin_cloudaeye_cloudaeye__implement", "mcp__cloudaeye__implement", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
---

## Queued Result

Submit the analysis once. An answer without `job_id` is the response itself
(report `status: error` and stop). With a `job_id`, call
`mcp__plugin_cloudaeye_cloudaeye__get_job_result(job_id, wait_seconds=110, since=<last progress_id>)`
again and again, with no pause, while `status` is `queued`, `running` or
`retrying`. The server keeps each call open while the job runs.

- Print `⏳ ` + `message` only when `progress_id` changed, exactly as given: no
  job ids, no "polling", no commentary, never a line the server did not send.
- On `completed`, use its `result` as **the response** below, keeping the
  tool's fields. An inner `status: error` is a refusal, not a clean result.
- If the answer carries `next_run`, end with the heading
  `**To get more from the next run**` and each entry as a bullet, exactly as given.
- Stop after 150 calls or 30 minutes and say the job is still running, with its
  id. On `failed` or `error`, report it and stop. Never submit again to check
  progress, and finish the job before any edit, upload or other command on the
  same session.

## When to run

The prior review must have completed first. If it is queued/running/retrying,
poll its existing job ID and read its numbered findings before any session
upload or planning call. There is no `review_job_id` argument: `implement`
reads the saved report on the session. Do not overlap a review, planning,
editing, or re-inspection workflow on this session.

The user invoked `/cloudaeye:implement`, or asked you to fix findings from a CloudAEye review and wants the server's plan for them.

It plans fixes for findings **something else already found**. It never finds issues itself: with nothing on record for the session — no review yet, or the last one came back clean — it says so and points at `/cloudaeye:inspect`, `/cloudaeye:security` or `/cloudaeye:review`.

What it adds over you doing it directly is **blast radius**. You can see the diff and the file you are editing; the server has the AST graph across the whole repository, so the plan names the other call site with the same defect, the caller whose contract changes, and the test that asserts on the behaviour being fixed. If the user just wants a one-line fix applied, doing it yourself is the right call and costs nothing.

## Steps

1. Set up the session.

   Run exactly this one command, alone in its Bash call (that is what lets it run without asking the user for permission):

   ```bash
   sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae start
   ```

   Its first line is JSON. Call `mcp__plugin_cloudaeye_cloudaeye__start_session` with every field of that line, unchanged, and keep the answer as `SESSION`; its `session_id` is the one every later call takes.

   - `SESSION.gate` is `repository`: the repository is not connected to CloudAEye yet. Run `sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide connect-repository` and follow it.
   - The tool is unavailable, or `status` is `error`: stop and tell the user to authenticate CloudAEye through `/mcp`.
   - `SESSION.upload_needed` is `false`: the server already has this exact change. Skip the upload.
   - Otherwise upload the change: exactly this one command, alone in its Bash call, with `SESSION` as JSON inside single quotes. The script checks the values itself and never prints a token.

     ```bash
     sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae upload '<SESSION as JSON>'
     ```

   Read the summary lines — the upload's when it ran, the first command's when it was skipped — and don't re-derive them:

   | output | what to do with it |
   |---|---|
   | `cloudaeye_error=…` | Stop and report it. Never print `upload_token` or `key_token`. |
   | `diff_bytes=0` | Nothing pending. Say so and stop — a plan for a change that no longer exists cannot be applied. If the user committed since the review, say that too. |
   | `base_source=fork_point` | The right baseline: the fork point off the integrated branch, not its tip. Name the branch and `base_age`; a very old baseline may miss newer merged work. |
   | `base_source=head` | Degraded: only working-tree edits are in the diff. Say so. If `SESSION` carries `setup_required`, report its `reason` and `remedy` as written; never quote `target_branch_error`, which names an internal record. |
   | `upload_http=` not `200` | The diff never reached the server. Stop; otherwise a stale result can look clean. |

   **Which baseline applied must reach the user.** Every degradation still produces output that looks correct, so silence about it is the one failure mode that misleads.
2. Call CloudAEye's `implement` MCP tool with:
   - `session_id`: `SESSION.session_id`
   - `request`: what the user said, **verbatim**. Three forms, and you pass through whichever they used rather than converting between them:

     | They said | You pass |
     |---|---|
     | `/cloudaeye:implement [1,3]` | `"[1,3]"` |
     | `/cloudaeye:implement [1,3] use a context manager` | the whole string — the numbers select, the rest binds the plans |
     | `/cloudaeye:implement` with no argument, or "fix them" | `""` — empty means every finding |
     | "fix the 2nd point", "just the criticals" | the sentence as they said it |

     Do not summarise it, do not expand a sentence into numbers yourself, and do not invent a list when they gave none. Which findings they mean *and* any constraint on the fix both live in the phrasing, and a summary drops the constraint first.

   The numbers are the ones the review printed, which are the server's own — so it resolves them against its stored report exactly, with no interpretation. That is why you must never renumber a findings list when you print it.

   Call `mcp__plugin_cloudaeye_cloudaeye__implement`; it is pre-approved in this skill's frontmatter.

   Do **not** send the findings themselves — the server reads its own saved report, which is more complete than what came back over the wire. Do not read the changed source files first either; the server has them staged and its own tooling to trace through them.
3. Finish the Queued Result polling step, then handle the original response
   before touching any code. The MCP job returns plans, never applied edits.
   - **`error`** — report it as written. It means no findings are on record; the fix is to run a review first, which the message already says.
   - **`needs_clarification`** — the request was ambiguous and **nothing was planned**. Ask the user which finding they meant, using the candidates in the message, and stop. Do not pick one yourself: a wrong guess edits the wrong code with the user's apparent blessing.
   - **`plans` empty with `unresolved`** — the request did not match any finding. Show `available_numbers` and ask.
   - **An `error` naming a number that does not exist** — a typo in the list. Report it and stop; the message carries the valid range. Do not re-send a trimmed list on the user's behalf: they asked for something specific and got it wrong, and quietly doing less is worse than saying so.
   - **Otherwise, show `resolved` first** — open with `Numbers read from <numbers_from>'s list:`, then one line per finding, each with its `n`, so the user can see the numbers they gave map to the findings they meant. Every command numbers its own list, and the last one shown wins: if the user meant another command's numbers, stop and tell them to run that command again (it answers from what is stored) before `/cloudaeye:implement`. With an explicit list this is a confirmation; with free text it is the reading, and the reading is the part that can be wrong.
   - **Before the first edit, name every file the plans will touch** that the findings did not name (a new module, a test file, a fixture), in one line. The user agreed to fix findings, not to a refactor they have not seen.
   - **`note`** — present when the code has changed since the review that produced these findings, which is the normal case once you have fixed one thing and come back for the next. Say it in one line before you start editing. Every plan was checked against the current source; this is what makes an *unmarked* plan mean something rather than nothing.
   - A plan marked **`stale`** points at code that has moved since the review. Say so and ask before applying it; it may already be fixed.
   - A plan with **`risk: not_an_edit`** cannot be fixed by changing code — a leaked credential needs rotating and revoking. Report the remedy; do not write a code change that pretends to fix it.
4. Apply the plans, and only the plans.
   - Make exactly the edits described, honouring `constraints` as hard requirements.
   - Work through `blast_radius`. It names things outside the diff — other call sites with the same defect, callers whose contract changes, tests that assert on the old behaviour. Check each one, and tell the user what you did about it. Ignoring it wastes the only thing this call bought.
   - Do not fix findings that were not planned. The user asked for these.
   - Anything under `out_of_scope` is not a CloudAEye finding — handle it as ordinary work, separately, and say that's what you're doing.
   - Run the tests only as the repository already runs them. **Never create a virtual environment, install packages or change the environment without asking first**; if the tests cannot run as things are, say so and what they need.
5. Close the loop.
   - Tell the user what you changed, and suggest re-running the review that produced the findings (`/cloudaeye:inspect`, `/cloudaeye:security` or `/cloudaeye:review`) to confirm the fix landed and introduced nothing new.
   - When they do, pass `next_intent` from this response as the `intent` — verbatim if you followed the plan, edited in the same plain words if you deviated. It names what was addressed and what was deliberately left, which is the only channel the reviewer has for that. Do not print it unless the user asks.

## Notes

- **Single-shot** — one request, one set of plans. If the user then wants different findings fixed, invoke the skill again; the server resumes the same session.
- **It plans; it never patches.** The server returns instructions, not file contents. You write the code — you have the working tree and the test runner, and it does not.
- **No verdict, and no finding is closed by fixing it.** Only re-running the review can say a fix worked, and you are the one who wrote the code being reviewed. Do not report the findings as resolved on the strength of your own edit.
- **The plan can be wrong.** It is a model reasoning over a code graph. When it contradicts something you have directly read in the source, say so rather than deferring to it — and prefer the file you read.
- Fixing a finding without this skill is entirely fine. Reach for it when the fix has reach beyond the file, or when the user asks for it by name.
- If `implement` is unavailable (MCP not connected), warn the user and offer to fix the findings directly from what the review already reported.
