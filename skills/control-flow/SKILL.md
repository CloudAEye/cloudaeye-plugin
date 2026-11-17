---
name: control-flow
description: Draw what the uncommitted changes in this repo did to the flow of control, as a mermaid sequence diagram with every message marked added, removed or retargeted. The arrows are resolved from the repository's code graph rather than inferred from the diff. Reports; it never edits code.
when_to_use: Use when the user asks what the change does to the flow, wants a sequence diagram for a PR description, or asks which components now talk to each other and in what order. For a prose summary of the change use /cloudaeye:describe instead.
allowed-tools: Read, Grep, Glob, LS
---

## Queued Result

Submit the analysis once. An answer without `job_id` is the response itself
(report `status: error` and stop). With a `job_id`, call
`mcp__plugin_cloudaeye_cloudaeye__get_job_result(job_id, wait_seconds=110, since=<last progress_id>, report="control-flow")`
again and again, with no pause, while `status` is `queued`, `running` or
`retrying`. The server keeps each call open while the job runs.

- Right before submitting, print:
  `⏳ CloudAEye is mapping what your change does to the flow of control. This can take a few minutes; progress shows below.`
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

**With a pull-request number** — `/cloudaeye:control-flow 412` or
`/cloudaeye:control-flow #412`, the same convention `/cloudaeye:review` takes —
find the repository as step 1 does, then call `start_session` with the same fields **and `pr_number`**
(the digits, with any `#` stripped) and `settings: "read"`, and skip the upload.
The server fetches that pull request and its diff itself. Then go to step 2.

Nothing here asks the user for a GitHub credential, and nothing should: the
server resolves the repository, its integrated branch and its App installation
from the tenant record behind the caller's OAuth token. A run that cannot reach
the repository is a server-side integration problem, reported as such — never a
prompt for a key.

**With no argument**, the diff is the working tree and step 1 applies.

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
   later call takes. In the same turn, Glob `**/.cloudaeye.config` and `**/.cloudaeye.rules` with `TOP` as
   the path: they are `SETTINGS_FILES`, each a path relative to `TOP`.

   - `SESSION.gate` is `repository`: the repository is not connected to CloudAEye yet. Read
     `${CLAUDE_PLUGIN_ROOT}/resources/skills/connect-repository.md` and follow it.
   - The tool is unavailable, or `status` is `error`: stop and tell the user to authenticate CloudAEye through `/mcp`.

   Upload the change with this one command, writing in `<TARGET>` (`SESSION.target_branch`),
   `<UPLOAD_URL>` and `<UPLOAD_TOKEN>` from `SESSION`, and one `-F 'settings_file=@<path>;filename=<path>'` for each of
   `SETTINGS_FILES`, at the end. It writes only under `.cloudaeye/`
   (which ignores itself) and leaves your git index as it was. It runs in `TOP`: when that is not
   the folder Claude Code is working in, put `cd '<TOP>' && ` in front of it. When `SESSION.target_branch` is
   empty, or the command stops at a `git` error before `curl` runs, read `${CLAUDE_PLUGIN_ROOT}/resources/skills/no-target-branch.md`
   instead.

   ```bash
   git -c credential.helper= fetch -q origin '<TARGET>' 2>/dev/null; mkdir -p .cloudaeye && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Upload-Token:%s"\n' '<UPLOAD_URL>' '<UPLOAD_TOKEN>' | tee .cloudaeye/upload.curl && git rev-parse --git-path index | xargs -I{} cp -p {} .cloudaeye/index && export GIT_INDEX_FILE=.cloudaeye/index && git add -N . && git diff --merge-base 'origin/<TARGET>' --output=.cloudaeye/session.diff -- . && git merge-base HEAD 'origin/<TARGET>' | curl -sS --fail-with-body -K .cloudaeye/upload.curl -F 'base_sha=<-' -F 'file=@.cloudaeye/session.diff' -F 'settings=read'
   ```

   It prints the upload's settings file, then the server's answer as JSON. Never print the upload token.

   | what came back | what to do with it |
   |---|---|
   | `curl: (22)` and an error | The diff never reached the server. Stop; otherwise a stale result can look clean. |
   | `diff_files` is `0` | Nothing pending — report "nothing to describe" and stop. |
   | `settings` | The team's settings that apply to this change (`SETTINGS`). Use `SETTINGS.control_flow`'s values as below. With no `settings`, none apply. |
   | `changed_files` | The changed paths (up to 20, `more_files` beyond). Take a file list from here, never from a git command of your own. |

   **Say which baseline applied:** the change against where this branch forked off
   `origin/<TARGET>`. Every degraded run still produces output that looks correct, so silence
   about it is the one failure mode that misleads.
2. Your settings — the `.cloudaeye.config` files in the repository that cover this
   change's files (files your team commits). On the working tree they are the upload's
   `settings`; on a pull request, `SESSION.settings`, read as its target branch has them. With
   neither, none apply.

   `control_flow.effort` and `control_flow.cross_repo` in them are your defaults;
   what the user asks for in this run wins. Print each of `problems` once. An
   `error` means use CloudAEye's defaults.

   Then call `mcp__plugin_cloudaeye_cloudaeye__control_flow` **once** (Claude Code asks before its
   first use) with `SESSION.session_id`, `depth` — the effort as hops:
   `low` 1, `medium` 2, `high` 3 — and `cross_repo` when the user or the settings
   give them, and `label` at its default — the tool docstring explains each. Two
   more arguments:

   - `context`: pass `{"scope_path": "<path>"}` only when the user scoped the
     run to a directory.
   - `post`: on a **pull request**, always `true` — the card goes on the pull
     request as a comment, as every CloudAEye command posts on a pull request,
     and a card already there for this commit is not posted again
     (`posted.already_posted`). On the working tree, `false`: there is nothing to
     post on.

3. Resolve the response using **Queued Result** above, including its
   synchronous rollout fallback and bounded polling deadline. Keep the same
   job ID throughout; never call `control_flow` again to check progress. Do not
   continue below until a usable original response has been obtained.

4. **On a pull request:** the card is on the pull request. Print a short summary —
   the card's opening line ("This code change …") as written, and the calls added,
   removed and moved — then *Posted on the pull request:* with `posted.url` (or the
   pull request's link when there is none), *already there for this commit* when
   `posted.already_posted`, or the delivery `status` and `note` when it is not `ok`.
   Offer to print the whole card here, then stop.

   **On the working tree:** first save the full report, which has the diagrams, with this one
   command:

   ```bash
   mkdir -p .cloudaeye/reports && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Report-Token:%s"\n' '<result.report.url>' '<result.report.token>' | tee .cloudaeye/report.curl && curl -sS --fail-with-body -K .cloudaeye/report.curl -o .cloudaeye/reports/control-flow.md && echo 'report_path=.cloudaeye/reports/control-flow.md'
   ```

   Then your final message is **the resolved response's `card`, exactly as given and whole** (it is
   the card as a terminal can show it: its opening "This code change …" line, the table and each
   flow's sentence), followed by one line, `Full report with diagrams: <report_path>` (on
   `report_error=…`, say the full report could not be saved and why). The card is the answer: a
   reply that is only the baseline line and the file path tells the developer nothing. Never open,
   read or print that file yourself.

   The fence is standard mermaid and stays mermaid: it is the same block that
   gets posted on the pull request, so what the developer reads here must be
   what their reviewer sees there. Do not redraw it as ASCII, flatten it for
   the terminal, or summarise the arrows in prose. If asked to render it: it
   renders in the artifact viewer, on GitHub, and in any markdown preview.

   The card is rendered server-side because what it may show is the feature.
   Four things it carries are invisible once reformatted away:

   - **it opens with one line beginning "This code change …"** — print it first
     and as written; it is the sentence a reviewer decides on;
   - **a facts table** — why this flow, what the call sequence did, how much of
     the change is *not* in the diagram, and the cross-repository line. Its
     "Changes not shown" row is the one number nothing else carries;
   - a call the code graph could not follow is a **dashed arrow to a named
     receiver**, explained in the legend — there is no list of them to print;
   - the footer says the diagram is structure, not a trace.

   **Two diagrams, under `### Before` and `### After`, whenever the call
   sequence moved** — additions included. Both declare the same participants
   in the same order, so one collaborator can be tracked straight down the
   page. Print both, headings included: dropping Before turns a comparison into
   a claim about the current code. They are **two states, not one sequence** —
   never read Before's arrows as part of After's flow, never number across
   them. A single diagram headed *"New — this symbol did not exist"* means the
   change created it: there is no Before to draw, and only the calls the new
   function itself makes are marked added.

   One diagram means one of two opposite things, and the opening line says
   which: the sequence is **unchanged**, or there was **no pre-edit graph** to
   compare against (`diff_measured: false`).

   **A `### Cross-repository reach` section**, when present, is a claim about a
   *different* codebase — never fold its counts into the flow's own — and it is
   the most consequential thing on the card: a caller in another repository
   this change breaks is something nothing else in a review would surface.
   Lead with it.

   These fields change what you may say around the card:

   | field | what to do with it |
   |---|---|
   | `unavailable` | An ordinary answer, not an error to retry. Print the `note` and stop. |
   | `diagrams: 2` | The card holds a Before and an After. Print both; describe them as two states. |
   | `diff_measured: false` | No pre-edit graph, so **every marker was suppressed** and there is no Before. Say what changed could not be determined. Never report it as "nothing changed". |
   | `drawn: 0` | The change has no single flow. The card explains it. Do not pick a flow yourself. |
   | `cross_repo.affected` | Callers in other repositories this change may break. Say how many, in how many repositories. |
   | `cross_repo.unmeasured` | The search **could not run**. Not "no callers found" — say it did not happen and why. |
   | `cross_repo.not_indexed` | Some connected repositories have no graph and could not be searched. Say how many; the one that breaks may be among them. |
   | `pr_url` | A pull-request run. **End with a link** — `[<repo>#<pr_number>](<pr_url>)`. Absent on a working-tree run: give no link, and never construct one. |
   | `posted.status` | Only `ok` confirms the card is on the pull request. `unavailable` or `failed` means it is not; `unknown` means delivery was not confirmed and will not be repeated automatically. Say so and why. Never write "posted" without reading this, and never re-enqueue to retry a post. |
   | `context_refresh.status` `skipped`/`failed` | The graph was not refreshed with this diff; the diagram may describe pre-edit code. Say so in one line and quote `context_refresh.reason`. |

## Notes

- Finish the current job before dependent planning/ticket actions. Do not
  overlap review, editing, or re-inspection workflows on the same session;
  dependent tools read the completed session report, not a pending job.

- **Single enqueue**: call the analysis tool once, poll that job, print its
  card, done. No re-enqueue or fix-and-retry loop.
- Good moments: before opening a PR; when a reviewer asks "what does this
  actually change about the flow?"; when a change touches several components
  and the ordering matters.
- **Line order is not execution order.** `alt` shows branches; early returns and
  exceptions are not modelled. The diagram is what the code is *shaped like*.
- **The arrows are not yours to add.** Every message was resolved from the
  symbol index. A missing one is an observation to state, not an edit to make.
- If `control_flow` is unavailable (MCP not connected), warn and skip — **do not
  draw a sequence diagram yourself from `git diff`**. A hand-drawn one is the
  guesswork this tool exists to replace, and nothing in it would say which
  arrows were verified.
