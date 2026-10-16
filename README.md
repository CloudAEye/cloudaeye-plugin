# CloudAEye for Claude Code

Pre-commit code review, security scanning, AI-slop scoring, change descriptions, questions, task verification, pull-request hygiene checks, docstring and unit-test generation, component ownership, issue explanation, tracking-issue creation, and fix planning for Claude Code.

## Commands

| Command | Purpose |
|---|---|
| `/cloudaeye:help` | List all available commands, or show how to use a specific command with its arguments, options, and examples. |
| `/cloudaeye:init` | Set up the current repository for CloudAEye review. Detects its provider, remote URL, and base branch, prompts for a monitor branch, and opens integration setup when needed. |
| `/cloudaeye:inspect` | Find bugs such as logic errors, missed edge cases, invalid inputs, concurrency problems, and broken code signatures. Returns an approval verdict and numbered findings with file locations and severity. |
| `/cloudaeye:security` | Find security issues across application code, LLMs, AI agents, and MCP tools, including secrets leaked in changed lines. Use for changes involving authentication, untrusted input, cryptography, prompts, or tool definitions. |
| `/cloudaeye:review` | Run all six report types in one comprehensive bug and security review. Use before opening a significant PR or when a large change needs more than the routine bug check. |
| `/cloudaeye:describe` | Turn the pending change into a Markdown description and a list of important changes for a PR body or commit message. Uses repository context to explain the impact across files. |
| `/cloudaeye:control-flow` | Draw sequence diagrams showing calls the change added, removed, redirected, or moved. Identifies affected callers in other connected repositories so you can see how the change alters execution flow. |
| `/cloudaeye:review-arch` | Show how a change affects the system architecture, repository layers, and dependencies through three diagrams. Reports architecture findings, cross-repository impact, and questions for a senior review. |
| `/cloudaeye:ask` | Answer questions about the pending change. Ask what else calls a function, how it behaved before, or where a similar pattern is used. |
| `/cloudaeye:check-task` | Verify whether the pending change fulfills a Jira ticket, GitHub issue, or written specification. Returns a DONE, PARTIAL, or NOT DONE verdict with details of missing work. |
| `/cloudaeye:check-pr` | Check an open PR's docstring and test coverage, README freshness, dependencies, title and description, duplicate code, and secrets. Runs the repository's configured checklist and posts the detailed report on the PR. |
| `/cloudaeye:implement` | Turn selected review findings into a fix plan. Identifies what to change, where to change it, and the affected callers, related defects, and tests. |
| `/cloudaeye:slop-score` | Assess how much manual review a change needs by checking nine code quality signals, including duplication, nonexistent APIs, dead code, missing tests, and overengineering. Returns a review band with supporting evidence. |
| `/cloudaeye:add-docs` | Generate docstrings for undocumented code in an open pull request and post them as review suggestions. Reports which suggestions were generated and which reached the PR. |
| `/cloudaeye:add-tests` | Generate unit tests for uncovered code in an open pull request, including new test files where needed. Posts the tests as review suggestions for you to review and run. |
| `/cloudaeye:create-owners` | Create an editable OWNERS.md using local Git history. No server or authentication required. Never overwrites existing ownership. |
| `/cloudaeye:explain` | Explain a Jira or GitHub issue using the code it touches. Describes the relevant components, their current behavior, and surrounding code so you can understand the work before implementing it. |
| `/cloudaeye:create-issue` | Turn selected findings from the last review into Jira tickets or GitHub issues, with an optional assignee and note. Returns ticket links and identifies findings already tracked in the same session. |

The review commands report results and do not edit code. `/cloudaeye:implement` leads to code edits, and even there the server only returns a plan — Claude applies it, and you re-run the review to confirm the fix landed. `/cloudaeye:create-owners` creates only the requested local ownership file.

Five commands require confirmation before their external writes: `/cloudaeye:add-docs` and `/cloudaeye:add-tests` post suggestions on a pull request, `/cloudaeye:control-flow` and `/cloudaeye:review-arch` can post their cards there when asked, and `/cloudaeye:create-issue` opens real tickets. Separately, `/cloudaeye:check-pr` posts its detailed report to the PR, and `/cloudaeye:explain` can also leave a comment on the issue.

## Command help

Run `/cloudaeye:help` to print the complete command table above, or
`/cloudaeye:help inspect` for a manual covering syntax, all supported arguments
and options, defaults, examples, output, and limitations. Full names such as
`/cloudaeye:help /cloudaeye:inspect` work too. Unknown names return the catalog
without running anything.

Help reads this README and the installed command's skill locally. It requires
no Git repository, authentication, network access, or running MCP server.

## Typical workflows

Every review command runs in one of two modes: with no argument it reviews your **uncommitted changes**, and with a pull-request number (`#412`) it reviews that **open pull request** — the server fetches the diff itself, so nothing is uploaded from your machine. The same command, the same output, two points in the cycle.

### Before you commit

```text
/cloudaeye:inspect                  after each task — the cheap bug pass; security is its own pass
/cloudaeye:implement [1,3]          plan fixes for findings 1 and 3; Claude applies them
/cloudaeye:inspect                  again, to confirm the fixes landed
/cloudaeye:check-task BETA-5225     does the change do what the ticket asked?
/cloudaeye:review                   bugs and security in one pass, before opening the PR
/cloudaeye:describe                 the PR body
```

`/cloudaeye:control-flow` shows what the change did to the order of calls, `/cloudaeye:review-arch` what it did to the layers and the boundaries between them, and `/cloudaeye:slop-score` how much careful reading it needs — all useful before a PR on a change you did not write line by line.

### Reviewer model options

`/cloudaeye:review`, `/cloudaeye:inspect`, and `/cloudaeye:security` use the
tenant's saved model and inversion settings by default. In Claude Code,
enabled inversion selects the configured GPT reviewer. Override only this run:

```text
/cloudaeye:review --invert-model false
/cloudaeye:inspect src/auth/ --high --model gpt
/cloudaeye:security --model-provider azure --model <model-id>
```

`--invert-model true|false` overrides the saved setting. `--model` accepts a
supported family or exact model ID; `--model-provider` selects its hosting
provider. An explicit model or provider takes precedence over inversion.
Available models, credentials, and plan restrictions are checked by the server;
an unavailable selection returns an error rather than silently switching models.
These options do not update saved configuration.

### After you push

```text
/cloudaeye:review #412              the full review, on the pull request
/cloudaeye:control-flow #412        before/after diagrams, and who in other repositories calls what changed
/cloudaeye:review-arch #412         the system, the repository's layers, what the change crossed, and what to ask before merging
/cloudaeye:check-pr #412            the hygiene checklist — description, title, docs, tests, dependencies
/cloudaeye:add-docs #412            docstrings, posted as suggestions on the pull request
/cloudaeye:add-tests #412           unit tests, posted the same way
/cloudaeye:create-issue [2] jira    file finding 2 as a Jira ticket (or `github`), optionally with an assignee
```

The pull request must be open, merge into your integrated branch, not come from a fork, and change at most 50 files. `/cloudaeye:implement` does not run on a pull request: its plans describe edits to a working tree.

Full details of every command — what to pass, what comes back, and how to read it — are in the [User Guide](https://docs.cloudaeye.com/user-guide/mcp/usage-guide.html).

### Component ownership

Run `/cloudaeye:create-owners` without arguments to create ownership files at the
repository root and in all non-ignored subdirectories, including empty directories.
Existing files are skipped; Git metadata and symlink directories are excluded.
An explicit directory limits creation to that directory only.

Run `/cloudaeye:create-owners src/payments` (or `.` for the repository root) to
generate an uncommitted `OWNERS.md` using local `git blame` on text files at HEAD.
There is no date or commit cap. Only Git and Python are needed. The directory must
already exist. Lead Maintainer and Team Members are populated directly: GitHub
noreply emails supply inferred @usernames, otherwise Git names/emails are used.
Confirm handles and replace names/emails before sharing; fill in unknown team/contact details.
Existing ownership is never overwritten. Shallow history produces a warning.
Each owner includes an ownership percentage: their share of current committed
text lines in that directory (including descendants). The author with the most
lines becomes the inferred lead. Blank lines and comments count; binary files,
symlinks, submodules, and OWNERS.md files do not. Uncommitted changes are ignored. The
denominator includes all contributors, not just the top three shown.

```markdown
# Component Ownership
- Lead Maintainer: @lead
- Team Name: Payments
- Team Members: @lead, @member
- Contact Slack: #payments
- Contact Email: payments@example.com
- Risk Level: normal
```

Edit the inferred owners before merging. This command only creates local
ownership files when explicitly invoked; it does not request reviews or add
webhook automation.

## Install

```text
/plugin marketplace add CloudAEye/claude-plugin
/plugin install cloudaeye
```

Restart Claude Code so the MCP server connects. If you previously installed the skills manually, remove those copies to avoid loading stale commands.

## Cursor

The same repository also packages a native Cursor plugin. It reuses `skills/`
and the bundled scripts; it does not duplicate review workflows. Cursor uses
`cursor/mcp.json` with the pinned `mcp-remote` OAuth bridge, which connects to
`https://api.cloudaeye.com/mcp`. The bridge registers a public native client with a
standard loopback callback for browser sign-in.
Its metadata is in `cursor/oauth-client-metadata.json`. OAuth and PKCE remain
required; no API key or client secret is bundled. Node.js and npm/npx must be
available. The first launch downloads the pinned bridge package.

From this repository, register the local plugin on Windows:

```powershell
.\scripts\install_cursor_plugin.ps1
```

The installer creates a real directory at `~/.cursor/plugins/local/cloudaeye`.
Cursor skips external junctions and symlinks. Existing installations are not
overwritten; use `-DirectoryName cloudaeye-manual` for an unused alternative.
Updates require refreshing the installed files. Restart Cursor, open Customize,
enable CloudAEye, and reload its MCP connection. The OAuth bridge opens browser
sign-in when authentication is needed. Select a skill from the `/` menu; do not
assume Claude's namespaced command spelling is used. No local MCP server is
needed. If CloudAEye was already added as a separate MCP connection, disable
that duplicate. Claude, Codex, and VS Code retain their
direct HTTP connection in `.mcp.json`.

Cursor-only compatibility guidance maps client-specific tool aliases to the
actual CloudAEye tools and resolves bundled script paths from the plugin
installation. Review scopes, job polling, and write-approval gates stay shared.

This package supports Cursor's native plugin format. See the
[Cursor plugin reference](https://cursor.com/docs/reference/plugins) for its
manifest and local installation conventions.

## Authenticate

1. Run `/mcp` in Claude Code.
2. Select CloudAEye and choose **Authenticate**.
3. Complete sign-in, organisation selection, and consent in the browser.
4. Run any `/cloudaeye:*` command in a Git repository with pending changes.

Claude Code stores and refreshes the OAuth credentials.

## Update

Every release bumps the `version` in [plugin.json](.claude-plugin/plugin.json); Claude Code only offers an update when it sees a newer one.

**Nothing prompts you by default.** Claude Code turns auto-update off for every marketplace that is not Anthropic's own, so a new CloudAEye release waits until you ask for it:

```text
claude plugin update cloudaeye@cloudaeye
```

Then run `/reload-plugins` in a terminal session, or start a new session. In the desktop app the plugin's MCP server — where the review tools live — reconnects only in a new session, so start one there; a release usually changes what that server offers, and a stale connection keeps the old tool list.

**To be prompted instead**, turn auto-update on for the CloudAEye marketplace once: `/plugin` → **Marketplaces** → `cloudaeye` → **Enable auto-update**. Claude Code then checks after each session starts, with a random delay of up to ten minutes, and when it has fetched a newer version shows a notification asking you to run `/reload-plugins`. If you ignore it, the new version loads on your next launch. The desktop app has no `/plugin` panel; use the command above there.

**Updating does not sign you out.** Credentials are stored against the server URL, and an update never changes it. If `/mcp` shows **Needs authentication** after an update, a token could not be refreshed — run **Authenticate** as above. Nothing about the update itself requires it.

`claude plugin list` shows the version you have.

## Self-hosted Server

The plugin uses `https://api.cloudaeye.com/mcp` by default. Set `CLOUDAEYE_URL` before starting Claude Code to use a self-hosted OAuth-enabled MCP endpoint.

For Cursor, replace the server URL in `cursor/mcp.json` before running the
installer. Use an HTTPS endpoint that supports OAuth.

## Data Flow

Each session-based review skill:

1. Detects the provider, repository URL, current branch, and base branch.
2. Calls the session-free `initialize_repository` tool; it opens setup only when the provider is not connected.
3. Calls the OAuth-authenticated `start_session` tool after initialization.
4. Builds and uploads the diff with `git diff` after `git add --intent-to-add .` so untracked files are included.
5. Calls the requested MCP review tool with the returned session ID.
6. Keeps its returned `job_id` and polls `get_job_result` every 30 seconds
   until terminal, never re-submitting to check progress. On completion,
   renders the original tool dictionary under `result`, not a universal card.

Queued tools are `inspect_diff` (inspect/security/review profiles),
`describe_change`, `ask`, `implement`, `check_task`,
`review_arch`, `control_flow`, `slop_score`, and `explain`. The latter still
delegates issue analysis to CloudAEye's backend; its MCP worker follows that
same backend run. `wait_seconds` is retained but deprecated for `explain`.
`ask` remains an answer, not a review; `implement` returns plans, not edits.
`create_issue` returns ticket results directly, without a job ID or polling.

Wait for a review to complete before planning fixes or creating tickets from
its findings; do not overlap review/fix workflows on one session. Ticket and
PR-comment writes retain their approval gates. Report uncertain delivery
without automatically repeating the write. A completed job may still carry
an original refusal/error; expired saved results are not empty or clean work.

Initialization, session creation, and Git diff upload do not enqueue work.

`create-owners` runs locally without initialization, MCP, authentication, or network
access. It neither stages files nor uploads a working-tree diff.

The upload token is placed in a private temporary curl config, is not printed, and is deleted when the upload command exits. The `.cloudaeye/` scratch directory contains only gitignored session diff data. Previously stored credential files are neither read nor changed.

OAuth requires an interactive MCP client, so unattended CI and service-account support is outside this release.

## Troubleshooting

| Symptom | Fix |
|---|---|
| CloudAEye shows **Needs authentication** | Open `/mcp` and complete **Authenticate** |
| A skill says `start_session` is unavailable | Restart Claude Code so the updated MCP tools load |
| A command from the docs is missing, or its tool is reported unavailable | Your plugin is behind: `claude plugin update cloudaeye@cloudaeye`, then a new session — see [Update](#update) |
| `upload_http=401` | The upload grant is missing, invalid, or belongs to another session |
| `upload_http=000` | Check network access and the configured review server URL |
| `cloudaeye_error=insecure_url` | Use HTTPS, except for localhost development |
| `base_source=head` | Connect the repository integration to enable the configured target branch |

## Layout

```text
.claude-plugin/plugin.json   plugin manifest
.mcp.json                    OAuth MCP server registration
skills/<verb>/SKILL.md       commands, including local help
```

When adding a command, update the Commands table above and its skill's inputs
and behavior: help reads these as its reference. Also update the documentation
repository's `docs/user-guide/mcp/skills.md`, `usage-guide.md`, and
`docs/user-guide/code-review/self-hosting/mcp.md` so every command is discoverable.
