---
name: review-arch
description: Review what the uncommitted changes in this repo (or a pull request) did to the architecture — which layers and components the change touched, every dependency it added or removed, layer violations, new import cycles, new calls to outside systems, breaks another repository would feel, and the questions a senior engineer would ask. Reports; it never edits code and finds no bugs.
when_to_use: Use before opening or merging a pull request that adds a dependency, a new module, a new external system or crosses a layer, when a reviewer asks "does this fit the architecture", or when the user asks for an architecture review, a layer check, or "what does this change touch". For bugs use /cloudaeye:inspect; for the call sequence use /cloudaeye:control-flow.
allowed-tools: ["Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository", "mcp__plugin_cloudaeye_cloudaeye__start_session", "mcp__cloudaeye__start_session", "mcp__plugin_cloudaeye_cloudaeye__review_arch", "mcp__cloudaeye__review_arch", "mcp__plugin_cloudaeye_cloudaeye__get_job_result", "mcp__cloudaeye__get_job_result"]
---

Run the steps in order. Each shell step is **exactly the one command shown**, alone in its
Bash call, typed as written (no `cd`, no variables, nothing chained): that is what lets it run
without asking the user for permission. Run it from the repository.

Any `cloudaeye_error=…` line: report it and stop. Never print a token.

## 1. Check the repository is connected

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae preflight
```

It prints `provider`, `repo_url`, `branch` and `head`. Call `initialize_repository`
with `provider`, `repo_url` and an empty `monitor_branch`. Keep the answer as `INIT`.

- `ready` or `initialized`: go on. `INIT.repo_full` is the repository name from here on.
- Anything else (`branch_required`, `setup_required`, an error): read
  `${CLAUDE_PLUGIN_ROOT}/resources/skills/connect-repository.md` and follow it. Do not
  start a session until it ends in `ready` or `initialized`.

## 2. Start the session and send the change

Call `start_session` with `INIT.repo_full` and the `branch` and `head` step 1
printed. If the tool is unavailable or answers `status: error`, stop and tell the
user to authenticate CloudAEye through `/mcp`.

**A pull-request number was given** (`/cloudaeye:review-arch 412` or `#412`): also
pass `pr_number` (digits only) and skip the upload. The server fetches the pull
request itself. Never ask the user for a GitHub credential.

**No argument** (the working tree): upload the change. The argument is
`start_session`'s answer, the whole JSON object, inside single quotes:

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae upload '<the start_session answer as JSON>'
```

Read its two lines; do not re-derive them:

| output | what to do |
|---|---|
| `diff_bytes=0` | Nothing pending. Say "nothing to review" and stop. |
| `upload_http=` not `200` | The change never reached the server. Stop. |
| `base_source=fork_point` | Normal. Mention the target branch only if `base_age` is more than a few weeks. |
| `base_source=head` | Only working-tree edits are in the diff. Say so. If `start_session` returned `setup_required`, give its `reason` and `remedy` as written. |

## 3. Run the review

Print: `⏳ CloudAEye is reviewing what your change does to the architecture. This can take a few minutes; progress shows below.`

Call `review_arch` **once** with `session_id`. `post`: `true` on a pull request,
`false` on the working tree. `context`: `{"scope_path": "<path>"}` only if the
user named a directory.

It answers with a `job_id`. Then call
`get_job_result(job_id, wait_seconds=110, since=<last progress_id>, report="review-arch")`
again and again, with no pause, while `status` is `queued`, `running` or
`retrying`:

- Print `⏳ ` + `message` only when `progress_id` changed. Nothing else: no job
  id, no "polling", no commentary.
- Stop after 150 calls or 30 minutes and say the job is still running, with its id.
- `failed` or `error`: report it and stop. Never call `review_arch` a second time.

On `completed`, print `✅ CloudAEye finished.` and use `result` below. An inner
`status: error` is a refusal: report it.

## 4. Show the result

**Working tree.** First save the full report, which has the pictures and the
repository's layers (exactly this one command, alone in its Bash call):

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae report review-arch '<result.report as JSON>'
```

Then your final message is **`result.card` exactly as given and whole**: it is
already short text made for a terminal. Do not reformat it, renumber findings,
or add your own analysis. End it with one line: `Full report with diagrams:
<report_path>` (or, on `report_error=…`, that the full report could not be
saved and why). Never open, read or print that file yourself.

**Pull request.** The review is posted as a comment. Print the verdict line and
the findings from `result.card`, then *Posted on the pull request:* with
`posted.url`; say *already there for this commit* when `posted.already_posted`;
when `posted.status` is not `ok`, say it was not delivered and give `status`
and `note`. End with `[<repo>#<pr_number>](<pr_url>)` when `pr_url` is present.

Say these only when the field is present:

| field | say |
|---|---|
| `unavailable` | Print `note` and stop. This is an answer, not an error to retry. |
| `diff_measured: false` | What changed could not be compared with the code before it. Never "nothing changed". |
| `pre_existing` above 0 | That many violations were already in the touched files; they are counted, not listed. |
| `explain_failed` | The review is measured only; the questions were not answered. |
| `confirm_failed` | Pattern candidates could not be judged. Not a clean pattern check. |
| `model.labelling` `started`/`in_progress` | Parts are named by folder this time; names are being written and the next run has them. |
| `service_map.unconfirmed` | Those repositories only share a path with this service. They are not callers: never name them as one. |
| `cross_repo.measured: false` | Breaks in other repositories were not checked. |
| `context_refresh.status` `skipped`/`failed` | The review may describe the code before this change. Quote `context_refresh.reason`. |
| `next_run` | End with the heading `**To get more from the next run**` and each entry as a bullet, as given. |

`verdict` is `PASS`, `FINDINGS` or `FAIL`; `FAIL` comes only from a rule the
repository declared. Findings are numbered by the server:
`/cloudaeye:implement [1,3]` plans fixes for them.

If `review_arch` is unavailable (MCP not connected), say so and stop. Do not
review the architecture yourself from `git diff`.
