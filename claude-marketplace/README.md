# CloudAEye Plugin

**Govern code at AI speed.**

Coding agents are flooding engineering pipelines with massive PRs faster than teams can validate, prioritize, understand, and secure them. CloudAEye **Review Intelligence** brings intelligent code review and governance directly into your coding agent workflow, helping you ship code with confidence. In an independent open-source benchmark of AI code review tools, CloudAEye ranked #1 with a 66.7% F1 score, outperforming 20 other tools evaluated ([see the results](https://www.cloudaeye.com/products/code-review/benchmark-2026/)). And it’s free for developers.

With the CloudAEye plugin, you can automate code reviews and streamline your entire software development workflow.

Use `cloudaeye:ultrareview` to tell a low-risk PR that is approved for merge from one that needs a human review, `cloudaeye:review` to identify bugs and correctness issues, `cloudaeye:slop-score` to detect AI-generated code slop, and `cloudaeye:security` to identify OWASP security vulnerabilities. Validate implementations against original tasks and requirements with `cloudaeye:check-task`, analyze architectural impact with `cloudaeye:review-arch`, and perform control-flow analysis with `cloudaeye:control-flow`. You can also assess PR risk using `cloudaeye:risk-score`, which considers bug history, code churn, and incident trends.

Go beyond code reviews with AI-powered development assistance. Ask questions across your codebase and multiple repositories using `cloudaeye:ask`, generate tests with `cloudaeye:add-tests`, explain tickets to help new hires understand their work with `cloudaeye:explain`, generate fix suggestions for review comments with `cloudaeye:implement`, and automatically generate docstrings with `cloudaeye:add-docs`.

For engineering teams, CloudAEye provides additional workflow automation, including PR triage with `cloudaeye:triage-prs`, intelligent reviewer assignment with `cloudaeye:assign-reviewer`, and automated PR checklist enforcement with `cloudaeye:check`. Enterprise teams can also deploy CloudAEye in a **self-hosted environment** with SSO/SAML support, maintaining control over their infrastructure and security requirements.

The coding agent writes the code. CloudAEye helps you ship it with confidence.

## Get started

1. **Install the plugin** in Claude Code from Anthropic's plugin directory: run `/plugin`, find **CloudAEye** under **Discover**, and install it. Restart Claude Code.
2. **Sign in.** Run `/mcp`, select CloudAEye, choose **Authenticate** and finish in the browser. No account yet? [Sign up free](https://console.cloudaeye.com/auth/sign-up). Claude Code keeps you signed in.
3. **Connect your repository.** In your Git repository, run `/cloudaeye:init`. CloudAEye builds its picture of the code, which takes 10–15 minutes depending on the repository's size.
4. **Review.** Run `/cloudaeye:inspect` after each coding task, or `/cloudaeye:review` before you open a pull request.

The commands run in Claude Code opened in a Git repository, and need Git 2.30 or newer and `curl` (on Windows, Git for Windows provides both, and the Bash they run in).

**Claude Code asks before each new step, the first time.** The commands run no script of their own: a command finds your repository with a read-only `git` command, and a review uploads your change with one line of `git` and `curl` that Claude Code shows you before it runs. Choose **Yes, and don't ask again** for each; the upload line asks on your first two runs (the second time for the `.gitignore` it keeps in `.cloudaeye/`), and after that nothing is asked again in that repository, in any session. To allow CloudAEye's own tools in every repository at once, add `"mcp__plugin_cloudaeye_cloudaeye"` to `permissions.allow` in your Claude Code settings.

## Commands

| Command | Purpose |
|---|---|
| `/cloudaeye:help` | List the commands, or show how to use one with its arguments, options and examples. |
| `/cloudaeye:init` | Connect the current repository to CloudAEye and choose the branch it is compared against. |
| `/cloudaeye:inspect` | Find bugs: logic errors, missed edge cases, invalid input, concurrency problems, broken signatures. Returns a verdict and numbered findings. |
| `/cloudaeye:security` | Find security issues in application code, LLMs, AI agents and MCP tools, including secrets in changed lines. |
| `/cloudaeye:review` | Bugs and security in one full review, before a significant pull request. |
| `/cloudaeye:ultrareview` | Every review of a change in one run, with a merge verdict: approved for merge, or needs a human review and why. Covers bugs and security, AI slop, risk, architecture and control flow, plus the PR checklist on a PR and the task check when you name one. On a PR it suggests reviewers and posts the report as one comment. |
| `/cloudaeye:describe` | Describe the change for a PR body or commit message. |
| `/cloudaeye:control-flow` | Before/after sequence diagrams of the calls the change added, removed or moved, and who in other repositories calls them. |
| `/cloudaeye:review-arch` | What the change does to the architecture: services, layers and dependencies, with findings and questions for a senior review. |
| `/cloudaeye:ask` | Ask about the change: what calls this, how it behaved before, where a pattern is used. |
| `/cloudaeye:check-task` | Check the change against a Jira ticket, GitHub issue or written spec: DONE or NOT DONE, with what is missing. |
| `/cloudaeye:check` | Run the repository's PR checklist on an open PR (`#412`) and post the report there. |
| `/cloudaeye:implement` | Turn review findings into a fix plan: what to change, where, and what else it affects. |
| `/cloudaeye:slop-score` | How much careful reading a change needs: a score out of 100 from nine code-quality signals, with the findings. |
| `/cloudaeye:risk-score` | Whether an open PR needs a human reviewer, and why, from its files' history, its author's recent PRs and its AI slop. With no PR number it assesses your change before you push it. |
| `/cloudaeye:triage-prs` | Which PR to review next across every connected repository, and why. A note like "I have half an hour" steers it. Reads only. |
| `/cloudaeye:assign-reviewer` | Who should review an open PR, why, and what they should check. A note like "Tom is away" steers it. It requests the review from the recommended reviewer when they can review in the repository, and only suggests otherwise. |
| `/cloudaeye:create-owners` | Write `.OWNERS.md` files from git history: who writes each part of the code. Writes in your working tree; never commits. |
| `/cloudaeye:config` | Your team's settings, in a `.cloudaeye.config` file you commit: which checks ultrareview runs, the limits it may approve within and how many reviewers it assigns, the review's severity floor and skipped paths, and your own LLM. Also syncs your organisation's review rules into `.cloudaeye.rules`. |
| `/cloudaeye:add-docs` | Generate docstrings for an open PR and post them as review suggestions. |
| `/cloudaeye:add-tests` | Generate unit tests for an open PR and post them as review suggestions. |
| `/cloudaeye:explain` | Explain a Jira or GitHub issue using the code it touches. |
| `/cloudaeye:create-issue` | File review findings as Jira tickets or GitHub issues. |

- None of them edits your code. `/cloudaeye:implement` returns a plan, and Claude applies it.
- `/cloudaeye:help inspect` prints one command's full manual. It works offline, with no sign-in.
- With no argument a command reviews your **uncommitted changes**; with a pull-request number (`#412`) it reviews that **open pull request**, which must merge into your integrated branch, not come from a fork, and change at most 50 files.
- Asking about the same change twice costs nothing the second time; a new change runs again.
- Always type `/cloudaeye:ultrareview` in full: a bare `/ultrareview` is Claude Code's own command.

Every command in full: the [User Guide](https://docs.cloudaeye.com/user-guide/mcp/usage-guide.html).

## Typical workflows

### Before you commit

```text
/cloudaeye:inspect                  after each task — the quick bug pass
/cloudaeye:implement [1,3]          plan fixes for findings 1 and 3; Claude applies them
/cloudaeye:check-task PROJ-123      does the change do what the ticket asked?
/cloudaeye:review                   bugs and security in one pass, before opening the PR
/cloudaeye:ultrareview              every review at once, with a merge verdict and a results table
/cloudaeye:describe                 the PR body
```

### After you push

```text
/cloudaeye:review #412              the full review, on the pull request
/cloudaeye:ultrareview #412         the same on a PR, plus the checklist and reviewers; posted as one comment
/cloudaeye:risk-score #412          does it need a human reviewer, and why
/cloudaeye:assign-reviewer #412     who should review it; add a note like "Tom is away"
/cloudaeye:triage-prs               which PR to review next, and why
/cloudaeye:check #412               the hygiene checklist
/cloudaeye:add-docs #412            docstrings, posted as suggestions
```

## Team settings

Your team's settings live in `.cloudaeye.config` and `.cloudaeye.rules` files you commit: which checks ultrareview runs, the limits it may approve within and how many reviewers it assigns, the review's severity floor and skipped paths, your own LLM, and your organisation's review rules. `/cloudaeye:config` asks one question at a time and writes the answers, and syncs your organisation's review rules from the CloudAEye console into `.cloudaeye.rules`. Commit both.

- With neither file in the repository, every command uses CloudAEye's defaults.
- A file covers its own directory and everything below it, so a team can set stricter rules for one part of the code.
- Pull requests read the files from their target branch, so a pull request cannot loosen its own settings.

`review`, `inspect`, `security` and `ultrareview` also take `--model`, `--model-provider` and `--invert-model true|false` for one run, such as `/cloudaeye:inspect --model gpt`.

## What CloudAEye writes, and what leaves your machine

**Writes outside your machine**

- `check` posts its report on the pull request.
- `ultrareview` on a PR posts its whole report as one comment, edited in place when run again. It names reviewers and never requests them.
- `control-flow`, `review-arch` and `risk-score` post their card on a pull request, once per commit; the risk card is edited in place.
- `add-docs` and `add-tests` post suggestions on the pull request, and `create-issue` files tickets. All three ask first.
- `assign-reviewer` requests the review from the recommended reviewer when they can review in the repository, and from anyone else only when you name them.
- `config` writes only `.cloudaeye.config` and `.cloudaeye.rules` in your working tree, and never commits them. It sends their text to CloudAEye, which works out the change and sends back what to write.
- `create-owners` writes only `.OWNERS.md` files in your working tree, and never commits them. CloudAEye works them out and sends back what to write.
- `explain` may comment on a Jira issue.

**What leaves your machine**

- Commands on your changes upload a `git diff` of your change (new files included) with `curl`. The diff is taken through a copy of git's index in a gitignored `.cloudaeye/` folder, so your own index is never changed. The upload's address and its write-only token for this session are kept in `.cloudaeye/upload.curl`, which `curl` reads, so the command is the same on every run and Claude Code's "don't ask again" covers it.
- Review commands (`inspect`, `security`, `review`, `ultrareview`) and `control-flow` send your `.cloudaeye.config` and `.cloudaeye.rules` files with the change, so CloudAEye can apply your team's settings.
- Long reports (`review-arch`, `control-flow`, `risk-score`, `slop-score`, `ultrareview`) print a short version in the terminal and save the whole report, diagrams included, to `.cloudaeye/reports/<command>.md`, downloaded with `curl`; it never passes through the model.
- Pull-request commands (`#412`), `triage-prs` and `assign-reviewer` upload no code: CloudAEye reads GitHub itself. `assign-reviewer` sends any `.OWNERS.md` files in your working tree.
- `create-owners` runs `git blame` on your machine and sends only its line counts: how many lines each author wrote in each file and when, under the author's name and email address as git records them. No code and no commit messages; CloudAEye keeps a digest of each address, never the address. It sends your `.OWNERS.md` files too, so their Teams lines are kept.
- Nothing reads credentials from your machine. Your GitHub login comes from your CloudAEye sign-in. To review with your own LLM, enter your API key in the plugin's settings (**Your LLM API key**, under `/plugin` → CloudAEye): Claude Code keeps it in your system's credential store and sends it only to CloudAEye, on its own connection, never through the conversation. CloudAEye stores it encrypted with your session and stops using it after 24 hours. Left empty, the key saved in the CloudAEye console is used.
- Everything goes to `https://api.cloudaeye.com/mcp`. The commands contact no other host, except `git fetch` from your repository's own remote.

Sign-in needs an interactive client, so unattended CI is not supported yet.

## Update

Plugins from Anthropic's directory update with Claude Code's own updates, or with `claude plugin update cloudaeye`. Then start a new session (or run `/reload-plugins`). Updating does not sign you out, and `claude plugin list` shows your version.

## Self-hosted server

The copy in Anthropic's directory connects to `https://api.cloudaeye.com/mcp`. To use your own OAuth-enabled CloudAEye server, install from CloudAEye's own marketplace instead, where the server address is a setting (uninstall the directory's copy first):

```text
claude plugin marketplace add CloudAEye/cloudaeye-plugin
claude plugin install cloudaeye@cloudaeye --config url=https://<your-host>/mcp
```

or set it later with `/plugin configure cloudaeye@cloudaeye`, then start a new session. In Cursor, change the URL in `cursor/mcp.json`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| CloudAEye shows **Needs authentication** | Open `/mcp` and choose **Authenticate** |
| A command or its tool is missing | Update the plugin, then start a new session — see [Update](#update) |
| The upload fails with error 22 and `invalid upload token` | The upload grant belongs to another session: run the command again |
| The upload fails with error 6 or 7 | Check network access |
| The review says it used your last commit as its baseline | Connect the repository (`/cloudaeye:init`) so its integrated branch is used, and make sure `origin/<that branch>` exists in your clone |
| `error: unknown option 'merge-base'` | Update Git to 2.30 or newer |
| A command asks to approve a `git` step or an upload | Expected: the commands run plain `git` steps and uploads that Claude Code shows you first. Approve it, or choose to stop being asked |

## Privacy

How CloudAEye handles your data: [Privacy Policy](https://www.cloudaeye.com/privacy-policy.html) · [Terms](https://www.cloudaeye.com/terms.html). Questions: support@cloudaeye.com.

## License

MIT. See [LICENSE](LICENSE). The plugin is a client of the CloudAEye service, whose use is governed by the terms above. Working on the plugin itself? See [CONTRIBUTING.md](https://github.com/CloudAEye/cloudaeye-plugin/blob/release/CONTRIBUTING.md).
