---
name: init
description: Connect the current Git repository to CloudAEye using its detected GitHub, GitLab, or Bitbucket remote.
when_to_use: Use when the user runs /cloudaeye:init or asks to connect this repository to CloudAEye.
allowed-tools: ["Bash(sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae *)", "mcp__plugin_cloudaeye_cloudaeye__initialize_repository", "mcp__cloudaeye__initialize_repository"]
---

## Steps

1. Run the bundled repository preflight helper from the repository root:

   ```bash
   sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae preflight
   ```

   It returns `provider`, `repo_url`, `repo_full`, `base_branch`, and `branch_required`.
   Never guess between remotes, providers, or branches.

2. Call `mcp__plugin_cloudaeye_cloudaeye__initialize_repository` once with the
   detected `provider`, `repo_url`, and an empty `monitor_branch`. If it returns
   `branch_required`, ask `Branch to monitor [base_branch]:`; Enter keeps the
   displayed base branch. Set `BRANCH` to that answer (or the displayed base
   branch); if there is no base branch, require a non-empty answer. Rerun the
   helper with `--branch "$BRANCH"`, set `MONITOR_BRANCH` from that
   result, and retry initialization with `monitor_branch=MONITOR_BRANCH`. Once a
   `CONNECTION` is chosen (step 3), pass `connection=CONNECTION` on every later call.

3. Use the initialization result (or the retry result) from
   `mcp__plugin_cloudaeye_cloudaeye__initialize_repository`:

   - `ready` or `initialized`: report `INIT.repo_full` as initialized with
     `INIT.target_branch` and stop. This command never creates a session.
     When `INIT.demo` is true, this is CloudAEye's public demo repository: print
     `INIT.message` exactly as written, in a fenced `text` block, and stop. Never run
     the fork command it names; the developer decides.
   - `branch_required`: ask for a branch and retry once.
   - `connection_required`: several connections (GitHub connections or GitLab
     tokens) can see the repository. List each `INIT.connections` entry's `name`
     as a numbered list and ask `Connection to use [1]:`; Enter keeps 1. Never choose for the user. Set
     `CONNECTION` to the chosen entry's `id` (never its `name`) and retry once with
     the same `provider`, `repo_url` and `monitor_branch` plus `connection=CONNECTION`.
     If it answers `connection_required` again, report its `reason` and stop.
   - `setup_required`: validate and open `integration_url` using the native browser
     command below, then poll every 10 seconds for at most 30 attempts. Each poll
     must call initialization with the original `provider` and `repo_url`, the
     same `monitor_branch=MONITOR_BRANCH` and, once chosen, the same
     `connection=CONNECTION`; replace `INIT` with each response. Continue
     only after `INIT.status` is `ready` or `initialized`; stop on errors, conflicts,
     or timeout. Never treat `provider_connected` alone as success.
   - `error` or `integration_conflict`: report the error and stop.

   ```bash
   sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae open '<integration_url from the tool>'
   ```

Never call `start_session`, upload a diff, or handle credentials in `/cloudaeye:init`.
