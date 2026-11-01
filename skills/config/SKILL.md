---
name: config
description: Set how CloudAEye works in this repository — ultrareview's approval settings (which checks run, the hard limits it approves within, the most human reviewers it assigns, and your ultrareview instructions), the review's defaults, the control-flow map's effort and the triage OKRs — in a .cloudaeye.config file at the repository's root or in any directory. Every run first syncs your organisation's review rules into the root .cloudaeye.rules. One section at a time; you answer in your own words.
when_to_use: Use when the user runs /cloudaeye:config, or asks to change CloudAEye's settings, approval limits, number of reviewers, review rules or instructions, or to sync the review rules from the console.
argument-hint: "[directory] [rules]"
allowed-tools: ["Bash", "mcp__plugin_cloudaeye_cloudaeye__review_rules", "mcp__cloudaeye__review_rules"]
---

## Where the settings live

In the repository, as two markdown files that can sit in any directory:

- **`.cloudaeye.config`** — the settings;
- **`.cloudaeye.rules`** — the review rules.

A pair covers its own directory and everything below it. Most repositories need only the
pair at the root; a pair in `services/payments/` covers that directory and wins over the
root's, setting by setting. Instructions, paths never reviewed and rules add up from the
root down. When a change touches files under different settings, it gets whichever asks
for more review: the lowest limit, the most reviewers, a check left on unless every
file's settings turn it off. Triage reads the root file only.

A new file starts from the plugin's template, `${CLAUDE_PLUGIN_ROOT}/resources/config/`,
where every setting is commented out with its options beside it. **The files are meant to
be committed**: before a commit CloudAEye reads them from the working tree, and on a pull
request from its target branch, so a pull request cannot change its own settings.

## Steps

Start **every** Bash call in this skill with these three lines; shell state does not
carry between calls.

```bash
cd "$(git rev-parse --show-toplevel)" || exit 1
for c in python python3 py; do command -v "$c" >/dev/null 2>&1 && "$c" -c "" 2>/dev/null && { PY=$c; break; }; done
CE() { "$PY" "${CLAUDE_PLUGIN_ROOT}/scripts/cloudaeye_config.py" "$@"; }
```

Every `CE` command prints JSON. `{"error": …}` means nothing was written: say the
error in plain words and ask again; never retry with a value the user did not give.

### 1. Which repository

```bash
cd "$(git rev-parse --show-toplevel)" 2>/dev/null || { echo "repo=not_git"; exit 0; }
for c in python python3 py; do command -v "$c" >/dev/null 2>&1 && "$c" -c "" 2>/dev/null && { PY=$c; break; }; done
[ -n "$PY" ] || { echo "cloudaeye_error=python_not_found"; exit 1; }
"$PY" "${CLAUDE_PLUGIN_ROOT}/scripts/repository_preflight.py" 2>/dev/null || echo "repo=none"
"$PY" "${CLAUDE_PLUGIN_ROOT}/scripts/cloudaeye_config.py" show | "$PY" -c "import json,sys;d=json.load(sys.stdin);print('settings_files=' + ' '.join(([d.get('file', '')] if d.get('exists') else []) + d.get('elsewhere', [])))"
```

`repo=not_git`: the settings live in a repository — say so and stop. Keep `repo_full`
as `REPO`; with `repo=none` (no GitHub, GitLab or Bitbucket remote) the settings can
still be written, but the organisation's rules cannot be synced. `settings_files` lists
the `.cloudaeye.config` files the repository already has.

### 2. Sync your organisation's review rules — every run

Every `/cloudaeye:config` brings the review rules saved in the CloudAEye console into
the repository's root `.cloudaeye.rules` first, without asking: it is a read of the
console and a write of only the rules it owns. Call
`mcp__plugin_cloudaeye_cloudaeye__review_rules` with `repo`: `REPO` (skip this step
when `REPO` is unknown, and say why). An answer with `status: error` is printed as it
is (`setup_required` → run `/cloudaeye:init` first) and the sync is skipped; the
settings can still be changed. Otherwise pass the **whole** answer, unchanged, in one
Bash call:

```bash
CE sync-rules --file - <<'CLOUDAEYE_RULES_JSON'
<the review_rules answer, verbatim>
CLOUDAEYE_RULES_JSON
```

Say in one line what happened: `synced` rules, with `added` and `removed` by id, and
`yours` (rules the team wrote, kept as they were). `written: false` means the console
has no rules for this repository and none were synced before, so no file was created.
Synced rules are headed by their id (`r12`) and replaced by the next sync: they are
changed in the console, not here.

### 3. Which directory

A directory argument answers this; otherwise, when `settings_files` lists any outside
the root, name them, and ask exactly:

```text
Where should these settings apply?
  1. The whole repository (default)
  2. One directory and everything below it — type its path
```

Enter or `1` is the root (no `--dir`); a path is `--dir "<path>"`. Call the chosen
`--dir` (or nothing) `DIR` below. With the argument `rules`, go straight to step 5.

### 4. One section at a time

Run `CE show DIR` and go through its `settings` section by section, in this order
(Triage PRs only at the root — `show` leaves it out elsewhere):

| # | Section | Settings (key) |
|---|---|---|
| 1 | Ultrareview — checks | PR checklist (`ultrareview.checks.checklist`), Review — bugs and security (`ultrareview.checks.review`), AI slop score (`ultrareview.checks.slop`), Risk score (`ultrareview.checks.risk`), Architecture (`ultrareview.checks.architecture`), Control flow (`ultrareview.checks.control_flow`), Task check (`ultrareview.checks.task`) — on or off |
| 2 | Ultrareview — limits | Risk score (`ultrareview.limits.risk`), AI slop score (`ultrareview.limits.slop`) — 0 to 100; Review severity (`ultrareview.limits.severity`) — medium or low |
| 3 | Ultrareview — human reviewers | Assign human review (`ultrareview.assign_reviewers`) — true or false; Max human reviewers to assign (`ultrareview.max_reviewers`) — 1, 2 or 3 |
| 4 | Ultrareview instructions | `ultrareview.instructions` — plain sentences |
| 5 | Review | Severity floor (`review.severity_floor`) — all, critical, high, medium, low; Paths never reviewed (`review.skip`) |
| 6 | Control flow | Effort (`control_flow.effort`) — low, medium or high; Across repositories (`control_flow.cross_repo`) — yes or no |
| 7 | Triage PRs | OKRs (`triage.okrs`) — text, or a file in the repository |

For each section print a short table — **Setting | Now | Options** — where *Now* is the
setting's `value`; otherwise its `inherited` value followed by *(from
<inherited_from>)*; otherwise *CloudAEye's default*. Under it, one line of what the
section means:

1. *A check that is off is not run. With Review, AI slop score or Risk score off,
   nothing is approved automatically.*
2. *Hard limits: a change above any of them is never approved automatically. Some
   findings always need a human too, such as a leaked secret or a Critical issue.*
3. *Whether ultrareview names human reviewers when a change is not approved (true by
   default; with false the verdict still says a human must look), and the most people
   to assign. One is assigned unless your ultrareview instructions ask for more.*
4. *Anything else ultrareview should follow, in plain words — for example "Pull
   requests from the Platform team need two humans: one from the team, one from
   outside it." An instruction can ask for more review, never less. Team names are
   the ones in the Teams section of OWNERS.md. Instructions here add to those above.*
5. *The floor applies to /cloudaeye:inspect, /security and /review when you give no
   level; ultrareview ignores it. Paths never reviewed are relative to this directory
   and left out of the change before it is uploaded, before a commit only.*
6. *How much effort the control-flow map spends following calls, and whether it looks
   for callers in your other repositories.*
7. *The key results /cloudaeye:triage-prs weighs each pull request against.*

Then ask: *Change anything here? Reply in your own words ("risk 40, slop 50", "turn
off architecture"), "next" to keep it as it is, or "done" to finish.*

Turn the reply into commands, all of one section in one Bash call:

- a value → `CE set DIR KEY=VALUE …` (several pairs at once);
- back to the default (or to what it inherits) → `CE set DIR KEY=-`;
- an instruction or a path → `CE add DIR KEY "the text"`, one call each; to replace
  them all, `CE clear DIR KEY` first; to remove one, clear and add back the rest.

Write only what the user asked for, in their words for instructions — never reword an
instruction into a stricter or looser one. An answer that is not one of the options
comes back as an error naming them: say so and ask again; never pick the nearest
option. After the call, print the section's new values from the command's `values` in
one line, and go to the next section. "done" ends the questions: go to step 5.

### 5. Rules of your own

Ask: *Add a rule of your own? Say it in plain words, and the paths it applies to
if not everywhere under this directory — or "no".* For each one:
`CE add-rule DIR --heading "<a short title>" --text "<the rule, in their words>" --paths "api/,lib/"`
(paths relative to the chosen directory; leave `--paths` out for all of it).

### 6. What changed

Print:

- each file written (`file`), and each setting changed, as *before → after*;
- the rules synced or added;
- which commands read what:
  - `/cloudaeye:ultrareview` — the checks, hard limits, the most human reviewers, the ultrareview instructions, the rules, and the control-flow settings;
  - `/cloudaeye:inspect`, `/cloudaeye:security`, `/cloudaeye:review` — the severity floor, the paths never reviewed and the rules;
  - `/cloudaeye:control-flow` — the effort and the search across repositories;
  - `/cloudaeye:triage-prs` — the OKRs.
- one line: *Commit `.cloudaeye.config` and `.cloudaeye.rules` so your team uses them
  too. Pull requests read them from the target branch, so they apply to pull requests
  once merged there.*

## Rules

- Write only `.cloudaeye.config` and `.cloudaeye.rules`, only through `CE`, and never
  under `${CLAUDE_PLUGIN_ROOT}`. Never commit or push them yourself.
- Never change a setting the user did not ask about, and never put a secret, token or
  password in these files: they are committed.
- The limits are the user's own numbers. Never say how CloudAEye's scores are built
  or what its own limits are.
