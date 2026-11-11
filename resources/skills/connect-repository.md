# Connecting a repository (read only when `initialize_repository` did not answer `ready` or `initialized`)

`INIT` is the last answer from `initialize_repository`. `provider` and `repo_url` are the ones
`repository_preflight.py` printed. Keep calling with the same values until `INIT.status` is `ready`
or `initialized`; stop on an error, a conflict, or the timeout below.

## `branch_required`

Ask `Branch to monitor [base_branch]:`. Enter keeps the displayed base branch; with no base
branch, require an answer. Then:

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae preflight --branch '<the answer>'
```

Call `initialize_repository` again with `monitor_branch` set to the `monitor_branch` that printed.
Use that same value on every later call.

## `setup_required`

The repository is not connected to CloudAEye yet. Open `INIT.integration_url` for the user:

```bash
sh ${CLAUDE_PLUGIN_ROOT}/scripts/cae open '<integration_url>'
```

`quick_link=…` means no browser could be opened: give the user that link.

Tell the user to finish connecting in the browser. Then call `initialize_repository` every 10
seconds, at most 30 times, with the same `provider`, `repo_url` and `monitor_branch`.
`provider_connected` alone is not success: wait for `ready` or `initialized`.

## Anything else

Report `INIT.status` with its `reason` and `remedy` as written, and stop.
