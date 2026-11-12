# Connecting a repository (only when it is not connected to CloudAEye yet)

`INIT` is the answer that sent you here: `start_session`'s, with `gate: repository`, or
`initialize_repository`'s. `provider` and `repo_url` are the ones the skill's first command printed.
Call `initialize_repository` with them, and with `monitor_branch` (empty at first), until
`INIT.status` is `ready` or `initialized`; stop on an error, a conflict, or the timeout below. Then go
back to the skill: a command that starts a session calls `start_session` again with the same fields.

## `branch_required`

Ask `Branch to monitor [base_branch]:`. Enter keeps the displayed base branch; with no base
branch, require an answer. Then run `cae preflight --branch '<the answer>'` and call
`initialize_repository` again with `monitor_branch` set to the `monitor_branch` that printed. Use
that same value on every later call.

## `setup_required`

The repository is not connected to CloudAEye yet. Open `INIT.integration_url` for the user with
`cae open '<integration_url>'`. `quick_link=…` means no browser could be opened: give the user that
link.

Tell the user to finish connecting in the browser. Then call `initialize_repository` every 10
seconds, at most 30 times, with the same `provider`, `repo_url` and `monitor_branch`.
`provider_connected` alone is not success: wait for `ready` or `initialized`.

## Anything else

Report `INIT.status` with its `reason` and `remedy` as written, and stop.
