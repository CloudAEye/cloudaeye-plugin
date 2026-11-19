# CloudAEye plugin: privacy policy

Last updated: 19 November 2026

This policy covers the CloudAEye plugin for Claude Code and the CloudAEye service it connects to
(`https://api.cloudaeye.com/mcp`), run by CloudAEye. It describes what the plugin sends, what the
service keeps, for how long, and who else sees it. CloudAEye's website, sign-up and billing are
covered by the [CloudAEye privacy policy](https://www.cloudaeye.com/privacy-policy.html).

## What the plugin sends

- **Your code change.** A command on uncommitted work uploads that change's `git diff`, new files
  included. A command on a pull request uploads nothing from your machine: the service reads the
  pull request from your Git provider through the integration your organisation connected.
- **Your team's settings files**, when present: `.cloudaeye.config` and `.cloudaeye.rules`, sent
  with the change and read to apply your team's settings. They are not stored.
- **Ownership files.** `/cloudaeye:assign-reviewer` and `/cloudaeye:create-owners` send the
  `.OWNERS.md` files in your working tree.
- **Line counts from `git blame`**, for `/cloudaeye:create-owners` only: for each file, how many
  lines each author wrote and when, under the author's name and email address as git records them.
  No code and no commit messages. The service keeps a one-way digest of each email address, never
  the address itself.
- **Your own AI model key**, only if you enter one in the plugin's settings. Claude Code keeps it
  in your system's credential store and sends it only to the CloudAEye service.

The plugin reads no credentials from your machine and sends nothing to any other service. Reports
it downloads are saved in the repository's gitignored `.cloudaeye/` folder and stay there until
you delete them.

## What the service receives besides

- **Your sign-in.** You sign in with your CloudAEye account (OAuth). It identifies your
  organisation and your account. Some commands use your GitHub username, which the service takes
  from your sign-in and remembers for your account.
- **Repository context.** When you connect a repository with `/cloudaeye:init`, CloudAEye indexes
  its code so that reviews can see callers, definitions and history beyond the change. To answer a
  command it may also read issues, pull requests, review history and file history from your Git
  provider, and tickets from Jira, through the integrations your organisation connected.
- **Usage records.** For each command: which command ran, when, for which repository and pull
  request, its outcome, and how many AI model tokens it used.

## How it is used

Only to run the commands you ask for, show their results to you and your team, post the results
you ask to have posted on a pull request or ticket, and account for usage and billing. CloudAEye
does not sell personal information.

## AI model providers

To review code, the service sends the relevant code and context to the AI model provider configured
for your organisation in the CloudAEye console: CloudAEye's default provider, or a provider and key
your organisation supplies. That provider's handling of the data is governed by its own terms.

## Where results go

Results stay with you unless a command posts them. Pull-request commands post their reports and
suggestions on the pull request; `/cloudaeye:create-issue` files tickets; `/cloudaeye:explain` may
comment on a Jira issue; `/cloudaeye:assign-reviewer` requests a review on GitHub. Anything posted
stays under your Git provider's or tracker's control.

## How long it is kept

| Data | Kept |
|---|---|
| Uploaded changes, staged files, review results and `git blame` counts | deleted after 7 days without activity |
| The review session's record (repository, branch, the task you checked against) | deleted after 30 days without activity |
| Command results in the queue | removed after 7 days; the job record after 30 days |
| Your own AI model key | stored encrypted with the session, and not used after 24 hours |
| Settings files | not stored |
| Per-pull-request summaries (checklist results, suggested reviewers) | kept while your organisation uses CloudAEye, so a repeated command answers without running again |
| The repository index and usage records | kept while your organisation uses CloudAEye |

To have any of it deleted sooner, write to support@cloudaeye.com.

## Where it is stored

The hosted service runs in the AWS US East region. A self-hosted installation keeps its data in the
customer's own AWS account.

## Security

Connections to the service are encrypted in transit. Each organisation's data is kept apart from
every other organisation's, and a session can be read only by the account that started it.

## Children

The plugin and the service are not intended for anyone under 18.

## Changes

When this policy changes, the date at the top changes with it, and the plugin's repository keeps
every earlier version.

## Contact

support@cloudaeye.com
