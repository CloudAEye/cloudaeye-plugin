---
name: slop-score
description: Score the uncommitted changes in this repo — or one path of them, or an open pull request — for AI-slop signals, and report how much review the change needs, with the evidence behind it. Nine weighted signals — duplicate code, hallucinated APIs, dead code, missing tests, complexity, generic naming, boilerplate comments, overengineering, style inconsistency — plus the shape of the change. Reports a score out of 100, its review band and a card; it never edits code.
when_to_use: Use when the user asks how much slop is in a change, whether it looks AI-generated, whether it needs a careful manual read before merge, or asks for a slop score. Also useful on a large change whose per-file review came back clean but whose size does not look earned.
argument-hint: "[optional: a path, or a PR number like #5]"
allowed-tools: Read, Grep, Glob, LS
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
| `#405`, or bare digits like `405` | A pull request. First read `${CLAUDE_PLUGIN_ROOT}/resources/skills/pull-request-run.md`, and follow it where it differs from the steps. |
| anything else: `src/auth/login.ts`, `src/auth/` | Only the changes under that path. First read `${CLAUDE_PLUGIN_ROOT}/resources/skills/scoped-run.md`. |

Digits mean a pull request; a directory named `405` is written `./405`. Read the guides the
arguments call for, in one turn, before step 1.

There is deliberately **no severity flag.** A floor drops findings before they are counted, so every numerator would shrink while the denominators stayed put — the score would fall because less was reported rather than because less was wrong. The server refuses one for the same reason.

## Steps

1. Set up the session.

   Find the repository with this one read-only command. This skill runs no script, so Claude Code
   asks before the first run of a command it has not been allowed:

   ```bash
   git rev-parse --show-toplevel HEAD --abbrev-ref HEAD && git remote get-url origin
   ```

   It prints four lines: `TOP` (the repository's folder), `HEAD`, `BRANCH` and `ORIGIN`. An error
   (not a Git repository, no `origin` remote): stop and say CloudAEye needs a Git repository with a
   GitHub, GitLab or Bitbucket remote.

   Then call `mcp__plugin_cloudaeye_cloudaeye__start_session` with `repo_url` = `ORIGIN`, `provider`
   (`github` for github.com, `bitbucket` for bitbucket.org, `gitlab` for a GitLab host), `branch` =
   `BRANCH` and `head` = `HEAD`, and keep the answer as `SESSION`; its `session_id` is the one every
   later call takes.

   - `SESSION.gate` is `repository`: the repository is not connected to CloudAEye yet. Read
     `${CLAUDE_PLUGIN_ROOT}/resources/skills/connect-repository.md` and follow it.
   - The tool is unavailable, or `status` is `error`: stop and tell the user to authenticate CloudAEye through `/mcp`.

   Upload the change with this one command, writing in `<TARGET>` (`SESSION.target_branch`),
   `<UPLOAD_URL>` and `<UPLOAD_TOKEN>` from `SESSION`. It writes only under `.cloudaeye/`
   (which ignores itself) and leaves your git index as it was. It runs in `TOP`: when that is not
   the folder Claude Code is working in, put `cd '<TOP>' && ` in front of it. When `SESSION.target_branch` is
   empty, or the command stops at a `git` error before the upload runs, read `${CLAUDE_PLUGIN_ROOT}/resources/skills/no-target-branch.md`
   instead.

   ```bash
   git -c credential.helper= fetch -q origin '<TARGET>' 2>/dev/null; mkdir -p .cloudaeye && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Upload-Token:%s"\n' '<UPLOAD_URL>' '<UPLOAD_TOKEN>' | tee .cloudaeye/upload.curl && git rev-parse --git-path index | xargs -I{} cp -p {} .cloudaeye/index && export GIT_INDEX_FILE=.cloudaeye/index && git add -N . && git diff --merge-base 'origin/<TARGET>' --output=.cloudaeye/session.diff -- . && git merge-base HEAD 'origin/<TARGET>' | curl -sS --fail-with-body -K .cloudaeye/upload.curl -F 'base_sha=<-' -F 'file=@.cloudaeye/session.diff'
   ```

   It prints the upload's settings file, then the server's answer as JSON. Never print the upload token.
   An upload error (`(22)` and a message): the diff never reached the server. Stop; otherwise a stale result can look clean.

   | what came back | what to do with it |
   |---|---|
   | `diff_files` is `0` | Nothing pending — report "nothing to score" and stop. |
   | `changed_files` | The changed paths (up to 20, `more_files` beyond). Take a file list from here, never from a git command of your own. |

   **Say which baseline applied**, in one short line and nothing more, with no code
   formatting: *Baseline: <TARGET> at its fork point.* Every degraded run still produces output that looks correct, so silence
   about it is the one failure mode that misleads.
2. Call CloudAEye's `slop_score` MCP tool **once** with:
   - `session_id`: `SESSION.session_id`
   - `context`: `{"scope_path": "<the path>"}` when the run is scoped to a path, as the scoped-run guide says. Omit it otherwise.

   Do not pass `run_review: false`. It scores only what is already on disk, which on a fresh session is every signal unmeasured — a correct answer and a useless one.

   Call `mcp__plugin_cloudaeye_cloudaeye__slop_score`; it is Claude Code asks before its first use.

   The tool runs the `slop` review profile first so the signals have something to read, then does the arithmetic. Anything a previous `/cloudaeye:review` or `/cloudaeye:inspect` already computed **on this same diff** is reused rather than paid for again, so the second scoring of an unchanged change is nearly free. You do **not** need to read the changed files yourself — the server has them staged.

3. Resolve the response using **Queued Result** above, including its
   synchronous rollout fallback and bounded polling deadline. Keep the same
   job ID throughout; never call `slop_score` again to check progress. Do not
   continue below until a usable original response has been obtained.

4. Report the inner `result` to the user:

   - **First: a `degraded` block.** The review underneath ran with no post-edit source staged, so every signal read an empty file. **Report it as a failed run and stop — do not present the card, and never call it a low score.** The server does not cache a degraded run, so re-running once the cause is fixed gives a real answer.

   - **Save the card as a file too**, after printing it, with this one command:

     ```bash
     mkdir -p .cloudaeye/reports && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Report-Token:%s"\n' '<result.report.url>' '<result.report.token>' | tee .cloudaeye/report.curl && curl -sS --fail-with-body -K .cloudaeye/report.curl -o .cloudaeye/reports/slop-score.md && echo 'report_path=.cloudaeye/reports/slop-score.md'
     ```

     and end with `Saved: <report_path>`. Skip this when the result has no `report`.
   - **Print the resolved response's `card` exactly as it comes.** It is markdown (a heading, a table of the nine signals, the numbered findings): print it as markdown, **never inside a code block** — Claude Code colours a code block with its own theme, which is unreadable on a light terminal. Do not reformat it, do not drop rows, and do not re-order it. It is rendered server-side precisely because the rules about what may be shown are the feature: an unmeasured signal prints a dash and a reason rather than a bar at zero, and the header says when not every signal could be measured. Both are lost the moment the card is retyped.

   - **`band_source: "judged"`, when present.** The arithmetic's band was moved one step after a model weighed the evidence — `band_reason` says why and `arithmetic_band` is what it moved from. The card already prints all three; do not drop them when summarising, and do not present the judged band as if the arithmetic produced it. When the field is absent the band is the arithmetic's and there is nothing to explain.

   - **`total` is the score, out of 100, with `band` beside it.** Quote both as the card prints them (*60 / 100, High likelihood of low-quality code*). Never compute another number from the bars or the finding counts. State the score plainly: never call it uncalibrated, approximate or provisional, and add no notes on how complete each check is.

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
