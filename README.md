# CloudAEye for Claude Code

Code review, security checks and review intelligence in Claude Code — on your changes before you commit, or on an open pull request after you push.

## Commands

| Command | Purpose |
|---|---|
| `/cloudaeye:help` | List the commands, or show how to use one with its arguments, options and examples. |
| `/cloudaeye:init` | Connect the current repository to CloudAEye and choose the branch it is compared against. |
| `/cloudaeye:inspect` | Find bugs: logic errors, missed edge cases, invalid input, concurrency problems, broken signatures. Returns a verdict and numbered findings. |
| `/cloudaeye:security` | Find security issues in application code, LLMs, AI agents and MCP tools, including secrets in changed lines. |
| `/cloudaeye:review` | Bugs and security in one full review, before a significant pull request. |
| `/cloudaeye:describe` | Describe the change for a PR body or commit message. |
| `/cloudaeye:control-flow` | Before/after sequence diagrams of the calls the change added, removed or moved, and who in other repositories calls them. |
| `/cloudaeye:review-arch` | What the change does to the architecture: services, layers and dependencies, with findings and questions for a senior review. |
| `/cloudaeye:ask` | Ask about the change: what calls this, how it behaved before, where a pattern is used. |
| `/cloudaeye:check-task` | Check the change against a Jira ticket, GitHub issue or written spec: DONE or NOT DONE, with what is missing. |
| `/cloudaeye:check-pr` | Run the repository's PR checklist on an open PR and post the report there. |
| `/cloudaeye:implement` | Turn review findings into a fix plan: what to change, where, and what else it affects. |
| `/cloudaeye:slop-score` | How much careful reading a change needs: a score out of 100 from nine code-quality signals, with the findings. |
| `/cloudaeye:risk-score` | Whether an open PR needs a human reviewer, and why, from its files' history, its author's recent PRs and its AI slop. |
| `/cloudaeye:triage-prs` | Which PR to review next across every connected repository, and why. A note like "I have half an hour" steers it. Reads only. |
| `/cloudaeye:assign-reviewer` | Who should review an open PR, why, and what they should check. A note like "Tom is away" steers it; a review is requested only when you ask. |
| `/cloudaeye:create-owners` | Write `OWNERS.md` files from git history: who writes each part of the code. Runs locally; never commits. |
| `/cloudaeye:add-docs` | Generate docstrings for an open PR and post them as review suggestions. |
| `/cloudaeye:add-tests` | Generate unit tests for an open PR and post them as review suggestions. |
| `/cloudaeye:explain` | Explain a Jira or GitHub issue using the code it touches. |
| `/cloudaeye:create-issue` | File review findings as Jira tickets or GitHub issues. |

None of them edits your code. `/cloudaeye:implement` returns a plan, and Claude applies it.

**What writes outside your machine:** `check-pr` posts its report on the pull request; `add-docs`, `add-tests` and `create-issue` ask first; `control-flow`, `review-arch` and `risk-score` post their card only when you ask; `assign-reviewer` requests reviews only from people you name; `explain` may comment on a Jira issue.

`/cloudaeye:help inspect` prints one command's full manual. It works offline, with no sign-in.

## Typical workflows

With no argument a command reviews your **uncommitted changes**; with a pull-request number (`#412`) it reviews that **open pull request**.

### Before you commit

```text
/cloudaeye:inspect                  after each task — the quick bug pass
/cloudaeye:implement [1,3]          plan fixes for findings 1 and 3; Claude applies them
/cloudaeye:check-task PROJ-123      does the change do what the ticket asked?
/cloudaeye:review                   bugs and security in one pass, before opening the PR
/cloudaeye:describe                 the PR body
```

### After you push

```text
/cloudaeye:review #412              the full review, on the pull request
/cloudaeye:risk-score #412          does it need a human reviewer, and why
/cloudaeye:assign-reviewer #412     who should review it; add a note like "Tom is away"
/cloudaeye:triage-prs               which PR to review next, and why
/cloudaeye:check-pr #412            the hygiene checklist
/cloudaeye:add-docs #412            docstrings, posted as suggestions
```

The pull request must be open, merge into your integrated branch, not come from a fork, and change at most 50 files.

### Reviewer model options

`review`, `inspect` and `security` take `--model`, `--model-provider` and `--invert-model true|false` for one run, e.g. `/cloudaeye:inspect --model gpt`. Omitted options use your organisation's saved settings.

Every command in full: the [User Guide](https://docs.cloudaeye.com/user-guide/mcp/usage-guide.html).

## Install

```text
/plugin marketplace add CloudAEye/cloudaeye-plugin
/plugin install cloudaeye
```

Restart Claude Code so the MCP server connects.

**Cursor:** install through Cursor's [plugin flow](https://cursor.com/docs/plugins) and authenticate the CloudAEye MCP connection. It needs Node.js for the `mcp-remote` bridge, plus Git, Python, Bash and curl (Git Bash on Windows).

## Authenticate

1. Run `/mcp` in Claude Code.
2. Select CloudAEye and choose **Authenticate**.
3. Complete sign-in in the browser.

Claude Code stores and refreshes the credentials.

## Update

```text
claude plugin update cloudaeye@cloudaeye
```

Then start a new session (or run `/reload-plugins` in a terminal). Auto-update is off by default for marketplaces other than Anthropic's; turn it on under `/plugin` → **Marketplaces** → `cloudaeye`. Updating does not sign you out. `claude plugin list` shows your version.

## Self-hosted server

Set `CLOUDAEYE_URL` to your OAuth-enabled MCP endpoint before starting Claude Code; in Cursor, change the URL in `cursor/mcp.json`. The default is `https://api.cloudaeye.com/mcp`.

## What leaves your machine

- Commands on your changes upload a `git diff` (new files included). A gitignored `.cloudaeye/` folder holds the session's diff, and the upload token stays in a private temporary file.
- Pull-request commands (`#412`), `triage-prs` and `assign-reviewer` upload no code: CloudAEye reads GitHub itself.
- `create-owners` runs locally and sends nothing.

Sign-in needs an interactive client, so unattended CI is not supported yet.

## Troubleshooting

| Symptom | Fix |
|---|---|
| CloudAEye shows **Needs authentication** | Open `/mcp` and choose **Authenticate** |
| A command or its tool is missing | Update the plugin, then start a new session — see [Update](#update) |
| `upload_http=401` | The upload grant is missing or belongs to another session |
| `upload_http=000` | Check network access and the server URL |
| `cloudaeye_error=insecure_url` | Use HTTPS, except for localhost |
| `base_source=head` | Connect the repository integration so the configured branch is used |

## Layout

```text
.claude-plugin/plugin.json        plugin manifest
.cursor-plugin/, cursor/          the Cursor plugin
.mcp.json                         MCP server registration
skills/<verb>/SKILL.md            the commands, including help
scripts/                          local helpers: repository detection, OWNERS.md from git blame
```

Adding a command: add it to the Commands table above (help reads it), and to the documentation's Skills & Commands and User Guide pages.
