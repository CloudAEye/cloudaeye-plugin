# Working on the CloudAEye plugin

This repository holds two editions of the same plugin, on one branch, `main`.

| | Main edition | Release edition |
|---|---|---|
| Where | the repository root | `claude-marketplace/` |
| Installed from | CloudAEye's own marketplace (`.claude-plugin/marketplace.json`, source `./`) | Anthropic's plugin directory (repository `CloudAEye/cloudaeye-plugin`, plugin path `claude-marketplace`, branch `main`) |
| Shell steps | one pre-approved command, `scripts/cae`, which runs the Python helper scripts | plain `git` and `curl` lines that Claude Code shows and asks about; no script |
| Server address | the `url` setting (self-hosted servers: `--config url=…`) | fixed: `https://api.cloudaeye.com/mcp` |
| Also has | Cursor (`.cursor-plugin/`, `cursor/`), the scripts' tests | nothing that is not Markdown, JSON or an image |

## Why there are two

Anthropic's directory refuses, from an organisation it has not verified, any file that is not
Markdown, text, JSON, YAML or an image (so no scripts), an `allowed-tools` entry beyond Read, Grep,
Glob and LS, and an MCP address it cannot read without a setting (17 Nov 2026). Anthropic chooses who
is verified and nobody can apply. The main edition keeps the helper scripts, which pre-approve one
command and so ask fewer questions, and the server-address setting self-hosted customers use.

Claude Code installs the main edition from the repository root and reads skills only from its
`skills/` folder, so `claude-marketplace/` rides along unused. The directory reads only
`claude-marketplace/`.

## Rules

- **A change to a skill is made in both editions.** Their skills are worded differently (a `cae`
  step at the root, a `git` + `curl` line in `claude-marketplace/`), so a change is not a copy: make
  it in each. `tests/test_claude_marketplace.py` fails when the two stop offering the same commands.
- **The release edition passes the directory's rules.** `tests/test_claude_marketplace.py` checks
  them (file types, read-only `allowed-tools`, the fixed address, nothing that reads as `curl` piped
  into a program); `claude plugin validate claude-marketplace --profile directory` checks the rest.
  Only the portal's Validate applies the rules for unverified organisations.
- **`claude-marketplace/README.md` is the directory listing's description.** It is written for
  someone deciding whether to install. The root README is the main edition's.
- **`/cloudaeye:help` prints its README's `## Commands` table verbatim**, in each edition. Keep that
  heading and its two columns. Adding a command means a row in both READMEs, and on the
  documentation's Skills & Commands and User Guide pages.
- **What the plugin sends anywhere is listed under "What leaves your machine" in both READMEs.** The
  directory's security scan checks the plugin against it.
- **Versions.** One version for both editions: raise `version` in `.claude-plugin/plugin.json`,
  `.cursor-plugin/plugin.json` and `claude-marketplace/.claude-plugin/plugin.json` together, to the
  same number (`test_both_editions_carry_one_version`). The directory publishes a new version only
  after its own checks and a Publish click.
- **The server must be at least as new as what the release edition calls**: `repo_settings` for
  `/cloudaeye:config`, `create_owners` and the `blame` upload for `/cloudaeye:create-owners`, the
  settings files on the upload, `repo_url` as git prints it, the `X-CloudAEye-LLM-Key` header, and
  the one-call `ultrareview` tool (without it the skill runs each pass itself). The main edition
  runs on what CloudAEye's server has had since 16 Nov 2026.

## Checks before pushing

```bash
python -m pytest tests
```

```bash
claude plugin validate claude-marketplace --profile directory
```

To run the release edition against a local server, copy `claude-marketplace/` somewhere, set `url`
in the copy's `.mcp.json`, and run `claude -p "/cloudaeye:describe" --plugin-dir <copy>` (with
`--settings '{"enabledPlugins":{"cloudaeye@cloudaeye":false}}'` if the marketplace copy is installed).
The main edition takes the address as `--settings
'{"pluginConfigs":{"cloudaeye@inline":{"options":{"url":"<local>/mcp"}}}}'`.
