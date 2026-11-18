---
name: review-arch
description: Review what the uncommitted changes in this repo (or a pull request) did to the architecture — which layers and components the change touched, every dependency it added or removed, layer violations, new import cycles, new calls to outside systems, breaks another repository would feel, and the questions a senior engineer would ask. Reports; it never edits code and finds no bugs.
when_to_use: Use before opening or merging a pull request that adds a dependency, a new module, a new external system or crosses a layer, when a reviewer asks "does this fit the architecture", or when the user asks for an architecture review, a layer check, or "what does this change touch". For bugs use /cloudaeye:inspect; for the call sequence use /cloudaeye:control-flow.
allowed-tools: Read, Grep, Glob, LS
---

Run the steps in order. This skill runs no script: each shell step is the one plain `git` or
`curl` command shown, and Claude Code asks before the first run of a command it has not been
allowed. Never print a token.

## 1. Start the session

Find the repository with this one read-only command:

```bash
git rev-parse --show-toplevel HEAD --abbrev-ref HEAD && git remote get-url origin
```

It prints four lines: `TOP` (the repository's folder), `HEAD`, `BRANCH` and `ORIGIN`. An error
(not a Git repository, no `origin` remote): stop and say CloudAEye needs a Git repository with a
GitHub, GitLab or Bitbucket remote.

Call `start_session` with `repo_url` = `ORIGIN`, `provider` (`github` for github.com, `bitbucket`
for bitbucket.org, `gitlab` for a GitLab host), `branch` = `BRANCH` and `head` = `HEAD` — and
`pr_number` (digits only) for a pull request (`/cloudaeye:review-arch 412` or `#412`) — and keep
the answer as `SESSION`.

- `SESSION.gate` is `repository`: the repository is not connected to CloudAEye yet. Read
  `${CLAUDE_PLUGIN_ROOT}/resources/skills/connect-repository.md` and follow it.
- The tool is unavailable or answers `status: error`: stop and tell the user to
  authenticate CloudAEye through `/mcp`.

## 2. Send the change

**A pull request**: skip this step. The server fetches the pull request itself. Never ask
the user for a GitHub credential.

**Otherwise** upload the change with this one command, writing in `<TARGET>`
(`SESSION.target_branch`), `<UPLOAD_URL>` and `<UPLOAD_TOKEN>` from `SESSION`. It writes only under
`.cloudaeye/` (which ignores itself) and leaves your git index as it was. It runs in `TOP`: when that is not
   the folder Claude Code is working in, put `cd '<TOP>' && ` in front of it. When
`SESSION.target_branch` is empty, or the command stops at a `git` error before `curl` runs, read
`${CLAUDE_PLUGIN_ROOT}/resources/skills/no-target-branch.md` instead.

```bash
git -c credential.helper= fetch -q origin '<TARGET>' 2>/dev/null; mkdir -p .cloudaeye && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Upload-Token:%s"\n' '<UPLOAD_URL>' '<UPLOAD_TOKEN>' | tee .cloudaeye/upload.curl && git rev-parse --git-path index | xargs -I{} cp -p {} .cloudaeye/index && export GIT_INDEX_FILE=.cloudaeye/index && git add -N . && git diff --merge-base 'origin/<TARGET>' --output=.cloudaeye/session.diff -- . && git merge-base HEAD 'origin/<TARGET>' | curl -sS --fail-with-body -K .cloudaeye/upload.curl -F 'base_sha=<-' -F 'file=@.cloudaeye/session.diff'
```

It prints the upload's settings file, then the server's answer as JSON. `curl: (22)` and an
error: the change never reached the server. Stop.

| what came back | what to do |
|---|---|
| `diff_files` is `0` | Nothing pending. Say "nothing to review" and stop. |

## 3. Run the review

Print: `⏳ CloudAEye is reviewing what your change does to the architecture. This can take a few minutes; progress shows below.`

Call `review_arch` **once** with `SESSION.session_id`. `post`: `true` on a pull request,
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
repository's layers, with this one command:

```bash
mkdir -p .cloudaeye/reports && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Report-Token:%s"\n' '<result.report.url>' '<result.report.token>' | tee .cloudaeye/report.curl && curl -sS --fail-with-body -K .cloudaeye/report.curl -o .cloudaeye/reports/review-arch.md && echo 'report_path=.cloudaeye/reports/review-arch.md'
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
