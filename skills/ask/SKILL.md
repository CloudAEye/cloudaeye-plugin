---
name: ask
description: Ask a free-form question about the uncommitted changes in this repo and get an answer grounded in the repository's code graph — callers, definitions and usage traces, not just the diff text. Returns an answer, not a review, and never edits code.
when_to_use: Use for blast-radius questions ("what else calls this?"), "what did this do before?", "is this pattern used elsewhere?", or a second opinion the coding agent cannot give from its own context window.
argument-hint: "[question about the pending change]"
allowed-tools: Read, Grep, Glob, LS
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

The user invoked `/cloudaeye:ask`, or asked a question about the pending change that you cannot answer confidently from what you have already read. That second case is the important one: the server has the whole repository's AST graph indexed, and you have a context window. Questions worth handing over:

- **Blast radius** — "what else calls this?", "who depends on this interface?"
- **Prior behaviour** — "what did this function do before my change?"
- **Repo-wide patterns** — "is this error handled the same way elsewhere?", "do other callers already do this check?"
- **Second opinion on a specific line** — "is this lock actually protecting anything?"

Do **not** use it as a review. It returns no findings and no verdict. If the user wants problems found, that's `/cloudaeye:inspect` (bugs), `/cloudaeye:security` (security), or `/cloudaeye:review` (both).

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
   empty, or the command stops at a `git` error before `curl` runs, read `${CLAUDE_PLUGIN_ROOT}/resources/skills/no-target-branch.md`
   instead.

   ```bash
   git -c credential.helper= fetch -q origin '<TARGET>' 2>/dev/null; mkdir -p .cloudaeye && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Upload-Token:%s"\n' '<UPLOAD_URL>' '<UPLOAD_TOKEN>' | tee .cloudaeye/upload.curl && git rev-parse --git-path index | xargs -I{} cp -p {} .cloudaeye/index && export GIT_INDEX_FILE=.cloudaeye/index && git add -N . && git diff --merge-base 'origin/<TARGET>' --output=.cloudaeye/session.diff -- . && git merge-base HEAD 'origin/<TARGET>' | curl -sS --fail-with-body -K .cloudaeye/upload.curl -F 'base_sha=<-' -F 'file=@.cloudaeye/session.diff'
   ```

   It prints the upload's settings file, then the server's answer as JSON. Never print the upload token.
   `curl: (22)` and an error: the diff never reached the server. Stop; otherwise a stale result can look clean.

   | what came back | what to do with it |
   |---|---|
   | `diff_files` is `0` | No pending changes. **Do not stop** — unlike the review skills, a question about the existing code is still answerable. |
   | `changed_files` | The changed paths (up to 20, `more_files` beyond). Take a file list from here, never from a git command of your own. |

   **Say which baseline applied:** the change against where this branch forked off
   `origin/<TARGET>`. Every degraded run still produces output that looks correct, so silence
   about it is the one failure mode that misleads.
2. Call CloudAEye's `ask` MCP tool with:
   - `session_id`: `SESSION.session_id`
   - `question`: the user's question **verbatim**. Do not summarise it, do not expand it into a "better" question, do not split it into several. The phrasing is what they meant; a rewritten question gets a different answer to a question nobody asked. If the question was implicit in conversation ("wait, does that break the retry path?"), quote it as they said it.
   - `intent`: optional — one paragraph on what you just changed, if the question is about your edit. Context for the question, not its subject. Write it from your own working context; do not read `.cloudaeye/session.diff` or run `git diff` to compose it — the server already has the diff.
   - `context`: optional — only `pr_title` / `pr_description`.

   Call `mcp__plugin_cloudaeye_cloudaeye__ask`; it is Claude Code asks before its first use.

   You do **not** need to read the changed source files yourself first — the server has the post-edit contents staged and its own tooling to trace through them.
3. Report the response:
   - Print the `answer` field as-is. It is plain markdown written to be read directly.

   Check `context_refresh.status` first. On `skipped` or `failed` the stored code graph was not refreshed with this diff, so the answer is based on the pre-edit code plus the diff text alone — say so in one line and quote `context_refresh.reason`. It is usually an expired GitHub installation token, which the user has to fix server-side.
   - If the answer names files you have not read and the user's next step depends on them, offer to open them — don't silently re-derive the answer yourself.
   - `files_visited` shows what the answer is grounded in. Surface it when the answer is surprising or the user pushes back, so they can see the basis rather than take it on trust.

## Notes

- **Single-shot** — one question, one answer. If the user has a follow-up, invoke the skill again with the follow-up as the new question; the server resumes the same session.
- **The answer can be wrong.** It is a model reasoning over a code graph, not a compiler. When it contradicts something you have directly read in the source, say so rather than deferring to it — and prefer the file you read.
- **It answers; it does not review.** If the answer volunteers problems, that's a bonus, not the contract. Findings come from the review skills.
- Pre-commit: the diff is `git diff` (working tree vs `HEAD`). Committing moves `HEAD`; the session persists and its recorded `head` is refreshed on the next call.
- If `ask` is unavailable (MCP not connected), warn the user and answer from your own context instead, saying that's what you did.
