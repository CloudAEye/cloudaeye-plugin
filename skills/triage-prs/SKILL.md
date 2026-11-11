---
name: triage-prs
description: Pick the pull request you should review next, across every repository your team connected to CloudAEye, and say why. Each PR waiting on you gets a priority out of 100 from its tickets' urgency, what the changed code does and the OKRs it serves, its risk, and how much else depends on it; PRs whose next move is the author's are listed apart. A note in your own words ("I have half an hour", "skip the UI repo") steers the pick. With nothing requested from you, it lists the PRs nobody was asked to review. Reads only; writes nothing on GitHub or Jira.
when_to_use: Use when the user asks what to review next, which PR to look at, what is waiting on them, to prioritise or triage pull requests, or (with repo or all) for a team's whole PR queue. Not for whether one PR is risky (/cloudaeye:risk-score) or who should review one (/cloudaeye:assign-reviewer).
argument-hint: "[here | repo | all] [a note: 'I have half an hour'] [okrs:<file or URL>] [for:@login]"
allowed-tools: ["Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "mcp__plugin_cloudaeye_cloudaeye__triage_prs", "mcp__cloudaeye__triage_prs", "mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository"]
---

## Direct Result

`triage_prs` returns its card directly. Do not poll for it or expect a job ID, and
call it once per request: it reads every connected repository, so a run can take a
minute when nothing was read recently, and runs soon after reuse what it read. It
never runs a review or a risk analysis, so there is no other job to wait for.

## Steps

### 1. Read the arguments

Split `$ARGUMENTS` into:

| Word | Meaning |
|---|---|
| `here` | only PRs waiting on you in **this** repository |
| `repo` | every open PR of this repository, whoever it waits on (a lead's view) |
| `all` | every open PR of every connected repository (a lead's view) |
| `okrs:<path or URL>` | an OKR document to weigh the PRs against, as a preview |
| `for:@login` | someone else's queue, only when the user asks for it |
| anything else | the user's **note**, kept word for word as `NOTE` |

No scope word means `mine`: every PR waiting on you in every connected repository.
Never interpret the note yourself; the server applies it.

### 2. Find the user's GitHub username (for `mine` and `here`)

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae login
```

`REVIEWER` is what it prints after `author=`. Empty means leave it out: the
server finds it from the user's sign-in when it can. That command already tried
the GitHub CLI and the git address: never look the login up any other way (no `gh`
or `git` call of your own, which would ask the user to approve it); if the server
still needs it, it answers `login_needed` and you ask.

### 3. Your settings

When you are in a git repository, read the OKRs setting in its top-level
`.cloudaeye.config` (`/cloudaeye:config` writes it), in one Bash call:

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae config effective
```

`triage.okrs` in the answer is used when the user named no `okrs:`. An `error`, or no
`triage`, means there is none.

### 4. Read the OKR document, when one was named

The `okrs:` argument, or else `triage.okrs` from your settings — a file or URL in
backticks names a document, anything else is the text itself. A file: read it. A URL:
fetch it with your own tools. Keep its text, at most 12,000 characters, as `OKRS`. It is
a preview for this run and is never stored; without it the team's saved OKRs are used.

### 5. Connect this repository, for `here` and `repo` only

These two need the current repository. Run the bundled preflight helper and the
session-free initialization tool, as every operational CloudAEye command does:

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae preflight
```

Call `mcp__plugin_cloudaeye_cloudaeye__initialize_repository` with the detected
`provider`, `repo_url` and an empty `monitor_branch`, and keep its response as `INIT`.
Use `INIT.repo_full` as `repo`. If it does not answer `ready` or `initialized`, say the
repository is not connected and suggest `/cloudaeye:init`; stop. `mine` and `all` skip
this step: they read every repository the team connected.

### 6. Call `triage_prs`

Pass `reviewer=REVIEWER`, `scope` (`mine`, `here`, `repo` or `all`), `repo` for `here`
and `repo`, `note=NOTE`, `okrs=OKRS`, and `for_login` (no `@`) when the user asked for
someone else's queue.

- `status: login_needed`: ask once — *What is your GitHub username?* — and stop until the
  user answers; then call again with it as `reviewer`. The server remembers it for this
  account, so it is asked only once.
- `status: error`: report `error` and stop.
- `status: ok`: go on.

### 7. Print `card` verbatim

It is rendered server-side: the pick with *Why now* and *Look at*, the rest in order,
what is not your move yet, and what was not measured. Do not reorder, shorten or reword
it, and do not add priorities or reasons of your own. **The list is numbered by the
server, 1 the pick; never renumber it.** "The second one" or "number 3" is the PR whose
`rank` is that number; `#3` is a pull request's own number. When it is unclear which
the user means, ask.

| field | what to do with it |
|---|---|
| `pick` | The PR to review next, `rank` 1. Use it when the user says "ok, review it". |
| `queue` | The rest, in order, each with the `rank` the card prints. Use it to turn "the second one" into a PR. |
| `not_your_move` | PRs waiting on their authors. Already on the card. |
| `not_prioritised` | PRs whose code could not be read. Already on the card. |
| `unmeasured` | What was not measured. Not measured is not low priority: say so if the user leans on it. |
| `ai` | No AI model answered; the reasons are the facts. Say so in one line. |
| `labelling` | When `needed` lists repositories, see step 8. |

### 8. Offer the labelling pass, once

When `labelling.needed` is not empty and `labelling.started` is absent, ask once:
*N repositories have no component labels yet, which makes business impact less exact.
Label them in the background? It is a one-off AI cost per repository, billed to your
team.* On yes, call `triage_prs` again with the same arguments and `label=true`,
and print the new card. Never pass `label=true` without asking.

### 9. End there

Close with the pick's link. **Do not run the review yourself.** When the user asks to
review the pick, it is `/cloudaeye:review #<number>` in a checkout of that repository;
if this checkout is another repository, say so rather than reviewing the wrong one.

## Notes

- Nothing is written on GitHub or Jira. The only write anywhere is the labelling pass,
  and only after the user agrees.
- If `triage_prs` is unavailable (MCP not connected), warn and stop. **Do not rank pull
  requests yourself** from `gh pr list`.
