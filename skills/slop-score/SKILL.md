---
name: slop-score
description: Score the uncommitted changes in this repo — or one path of them, or an open pull request — for AI-slop signals, and report how much review the change needs, with the evidence behind it. Nine weighted signals — duplicate code, hallucinated APIs, dead code, missing tests, complexity, generic naming, boilerplate comments, overengineering, style inconsistency — plus the shape of the change. Reports a score out of 100, its review band and a card; it never edits code.
when_to_use: Use when the user asks how much slop is in a change, whether it looks AI-generated, whether it needs a careful manual read before merge, or asks for a slop score. Also useful on a large change whose per-file review came back clean but whose size does not look earned.
argument-hint: "[optional: a path, or a PR number like #5]"
allowed-tools: ["Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__start_session", "mcp__cloudaeye__start_session", "mcp__plugin_cloudaeye_cloudaeye__slop_score", "mcp__cloudaeye__slop_score", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
---

## Queued Result

Submit the analysis once. An answer without `job_id` is the response itself
(report `status: error` and stop). With a `job_id`, call
`mcp__plugin_cloudaeye_cloudaeye__get_job_result(job_id, wait_seconds=110, since=<last progress_id>, report="slop-score")`
again and again, with no pause, while `status` is `queued`, `running` or
`retrying`. The server keeps each call open while the job runs.

- Right before submitting, print:
  `⏳ CloudAEye is working out your change's AI slop score. This can take a few minutes; progress shows below.`
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

Nine signals, scored together out of 100, over the change: duplicate code, hallucinated API,
dead code, missing tests, high complexity, generic naming, boilerplate comments,
overengineering and style inconsistency.

The signals add up to a **score out of 100**, which the card prints with one of four bands. It is not yet validated against a labelled sample, and the card's footnote says so:

**Low likelihood of slop** · **Review recommended** · **High likelihood of low-quality code** · **Strong candidate for manual review before merge**

Reported beside the score and contributing no points: the volume of the change, how many changed functions carry a real behavioural edit, documentation drift, and commit shape. Volume is the *denominator* the other signals are measured against — a 1,200-line change is not slop, it is a 1,200-line change — which is why it is context rather than a scored signal.

## The one rule you must not break

**The band describes review burden, never authorship.** "Strong candidate for manual review before merge" is a claim about a change. "This was AI-generated" is a claim about a person, and this command does not make it — it would be wrong about copy-pasted human work as often as it was right. Report the score, the band and the evidence. Do not translate any of them into a statement about who or what wrote the code, even if the user's question was phrased that way.

## What the user typed

| Argument | What to do |
|---|---|
| *none* | The working tree: every uncommitted change. Go straight to **Steps**. |
| `#405`, or bare digits like `405` | A pull request. First run `sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide pull-request-run`, and follow it where it differs from the steps. |
| anything else: `src/auth/login.ts`, `src/auth/` | Only the changes under that path. First run `sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae guide scoped-run`. |

Digits mean a pull request; a directory named `405` is written `./405`. Each guide is that one
command, alone in its Bash call.

There is deliberately **no severity flag.** A floor drops findings before they are counted, so every numerator would shrink while the denominators stayed put — the score would fall because less was reported rather than because less was wrong. The server refuses one for the same reason.

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
   | `diff_bytes=0` | Nothing pending — report "nothing to score" and stop. |
   | `base_source=fork_point` | The right baseline: the fork point off the integrated branch, not its tip. Name the branch and `base_age`; a very old baseline may miss newer merged work. |
   | `base_source=head` | Degraded: only working-tree edits are in the diff. Say so. If `SESSION` carries `setup_required`, report its `reason` and `remedy` as written; never quote `target_branch_error`, which names an internal record. |
   | `upload_http=` not `200` | The diff never reached the server. Stop; otherwise a stale result can look clean. |

   **Which baseline applied must reach the user.** Every degradation still produces output that looks correct, so silence about it is the one failure mode that misleads.
2. Call CloudAEye's `slop_score` MCP tool **once** with:
   - `session_id`: `SESSION.session_id`
   - `context`: `{"scope_path": "<the path>"}` when the run is scoped to a path, as the scoped-run guide says. Omit it otherwise.

   Do not pass `run_review: false`. It scores only what is already on disk, which on a fresh session is every signal unmeasured — a correct answer and a useless one.

   Call `mcp__plugin_cloudaeye_cloudaeye__slop_score`; it is pre-approved in this skill's frontmatter.

   The tool runs the `slop` review profile first so the signals have something to read, then does the arithmetic. Anything a previous `/cloudaeye:review` or `/cloudaeye:inspect` already computed **on this same diff** is reused rather than paid for again, so the second scoring of an unchanged change is nearly free. You do **not** need to read the changed files yourself — the server has them staged.

3. Resolve the response using **Queued Result** above, including its
   synchronous rollout fallback and bounded polling deadline. Keep the same
   job ID throughout; never call `slop_score` again to check progress. Do not
   continue below until a usable original response has been obtained.

4. Report the inner `result` to the user:

   - **First: a `degraded` block.** The review underneath ran with no post-edit source staged, so every signal read an empty file. **Report it as a failed run and stop — do not present the card, and never call it a low score.** The server does not cache a degraded run, so re-running once the cause is fixed gives a real answer.

   - **Save the card as a file too**, after printing it (exactly this one command, alone in its Bash call):

     ```bash
     sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae report slop-score '<result.report as JSON>'
     ```

     and end with `Saved: <report_path>`. Skip this when the result has no `report`.
   - **Print the resolved response's `card` verbatim, inside a fenced code block.** Do not reformat it, do not turn it into a table, do not drop rows, and do not re-order it. It is rendered server-side precisely because the rules about what may be shown are the feature: an unmeasured signal prints a dash and a reason rather than a bar at zero, the header says when not every signal could be measured, and a partially built signal says so on its own row. Every one of those is lost the moment the card is retyped.

   - **`band_source: "judged"`, when present.** The arithmetic's band was moved one step after a model weighed the evidence — `band_reason` says why and `arithmetic_band` is what it moved from. The card already prints all three; do not drop them when summarising, and do not present the judged band as if the arithmetic produced it. When the field is absent the band is the arithmetic's and there is nothing to explain.

   - **`total` is the score, out of 100, with `band` beside it.** Quote both as the card prints them (*60 / 100, High likelihood of low-quality code*). Never compute another number from the bars or the finding counts. The card says the score is not calibrated yet; say so too if the user leans on the exact figure.

   - **Never say how the score is built.** No weights, no points per signal, no "out of N points measured": the result does not carry them, on purpose. When `unmeasured` is not empty, say the score covers only the signals that could be measured, and name the others.

   - **Never report `unmeasured` as clean.** Each entry is a signal nothing looked at, which is a different statement from a signal that found nothing. If the user's question was "is this change slop?", an answer that quietly omits three unmeasured signals is not an answer. Name them and say why in one line — the card already carries the reason.

   - **The findings are numbered by the server.** Print them exactly as the card numbers them and never renumber. Those numbers are what the user types back at `/cloudaeye:implement [1,3]`, which resolves them in Python against the stored report.

   - **`scope`, when present.** Name the path and how many changed files were left out, and say that duplicate code and hallucinated APIs are weaker under a scope.

   - Then say what you would do about it, in one or two sentences grounded in the highest-scoring rows — not in the band name. A 60 driven by duplicate code and a 60 driven by missing tests call for different work, and the band cannot tell them apart.

   - If there are findings, offer `/cloudaeye:implement [n]` for a plan on the ones the user picks. Do not start editing until they reply.

## Notes

- Finish the current job before dependent planning/ticket actions. Do not
  overlap review, editing, or re-inspection workflows on the same session;
  dependent tools read the completed session report, not a pending job.

- **The score is arithmetic; only the band is judged.** Every point traces to a finding with a file and a line, which is why the card can be argued with. If the user disputes a row, look at the evidence under it rather than defending the row. The one model judgment is the band, it can move by one step at most, and its reason is printed — so that is also arguable rather than an oracle.
- **A low score is not an approval.** These nine signals are about the shape of a change, not its correctness — a change can be perfectly clean here and still be wrong. For bugs run `/cloudaeye:inspect`, and for the security surface `/cloudaeye:security`. Say this when the user reads a low score as "good to merge".
- **Volume is context, not a signal.** The headline reports lines, files and how many changed functions carry a real behavioural edit. "1,200 lines, 65 files, two behavioural changes" is the shape the whole feature exists to make visible, and it contributes no points on purpose — a big change is not a bad one.
- **Commit shape is reported absent, never clean.** A session carries no commit list, so the "one enormous commit, generic message" signal cannot be measured here and says so rather than passing.
- **Generated and vendored files are excluded**, and the exclusion is reported. Lockfiles and generated output are the reason a "1,200 lines changed" headline is usually wrong.
- **A scored run saves its report,** so `/cloudaeye:implement` works on the findings straight afterwards, and a later `/cloudaeye:review` on the same diff reuses the stages this run paid for.
- This is a **single-enqueue** skill: call the analysis tool once, poll that job, report its output, done. No re-enqueue or fix-and-retry loop inside the skill.
- If `slop_score` is unavailable (MCP not connected), warn the user and skip.
