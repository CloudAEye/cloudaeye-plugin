---
name: config
description: Set how CloudAEye works in this repository — ultrareview's approval settings (which checks run, the hard limits it approves within, and its human review policy — auto-assigning reviewers, how many at most, and your instructions), the review's defaults and which LLM reviews the code, the control-flow map's effort and the triage OKRs — in a .cloudaeye.config file at the repository's root or in any directory. Every run first syncs your organisation's review rules into the root .cloudaeye.rules, and a repository with no settings file yet can start from the ultrareview settings saved in the console. One section at a time; you answer in your own words.
when_to_use: Use when the user runs /cloudaeye:config, or asks to change CloudAEye's settings, approval limits, number of reviewers, review rules or instructions, the review's LLM or model, or to sync the review rules from the console.
argument-hint: "[directory] [rules]"
allowed-tools: Read, Grep, Glob, LS
---

## Where the settings live

In the repository, as two markdown files that can sit in any directory:

- **`.cloudaeye.config`** — the settings;
- **`.cloudaeye.rules`** — the review rules.

A pair covers its own directory and everything below it. Most repositories need only the
pair at the root; a pair in `services/payments/` covers that directory and wins over the
root's, setting by setting. Instructions, paths never reviewed and rules add up from the
root down. When a change touches files under different settings, it gets whichever asks
for more review: the lowest limit, the most reviewers, a check left true unless every
file's settings make it false. The LLM settings and triage read the root file only. A
yes-or-no setting is written `true` or `false`.

A new file starts from CloudAEye's template, where every setting is commented out with its
options beside it. **The files are meant to be committed**: before a commit CloudAEye reads
them from the working tree, and on a pull request from its target branch, so a pull request
cannot change its own settings.

## How this skill reads and writes them

This skill runs no script, so the settings files' rules run on CloudAEye's server:
`mcp__plugin_cloudaeye_cloudaeye__repo_settings` takes the files' text (`FILES`, below) and a
command, and answers with what to write. It writes nothing itself.

- `RS <command> …` below means: call `repo_settings` with `command`, `files` = `FILES`, and the
  arguments named.
- `status: error`: nothing is to be written. Say the `error` in plain words and ask again;
  never retry with a value the user did not give.
- **Apply every entry of `writes`** before anything else: with `new_file: true`, Write `text` to
  `TOP/<path>`; otherwise, for each of `edits` in order, Edit `TOP/<path>` replacing
  `old_string` with `new_string` exactly. If an Edit does not apply, Write the whole `text`
  instead. Then set `FILES[<path>]` to `text`, so the next call sends the file as it now is.
  Claude Code asks before the first edit; nothing else is ever written.

### 1. Which repository

Find it with this one read-only command (Claude Code asks before the first run of a command it
has not been allowed):

```bash
git rev-parse --show-toplevel && git remote get-url origin
```

The lines are `TOP` (the repository's folder) and `ORIGIN`. An error on the first: the
settings live in a repository — say so and stop. `REPO` is `owner/name` from `ORIGIN` (the path
after the host, without `.git`); with no `origin` remote, the settings can still be written, but
the organisation's rules cannot be synced.

Then Glob `**/.cloudaeye.config` and `**/.cloudaeye.rules` with `TOP` as the path, and Read every
file found, in one turn. `FILES` maps each one's path from `TOP` (forward slashes) to its text,
exactly as read, without the line numbers Read shows. With none, `FILES` is `{}`.

### 2. Sync your organisation's review rules — every run

Every `/cloudaeye:config` brings the review rules saved in the CloudAEye console into the
repository's root `.cloudaeye.rules` first, without asking: it is a read of the console and a
write of only the rules it owns. Call `mcp__plugin_cloudaeye_cloudaeye__review_rules` with
`repo`: `REPO` (skip this step when `REPO` is unknown, and say why). An answer with
`status: error` is printed as it is (`setup_required` → run `/cloudaeye:init` first) and the sync
is skipped; the settings can still be changed. Otherwise `RS sync-rules` with `answer` = the
**whole** answer, unchanged, and apply `writes`.

Say in one line what happened: `synced` rules, with `added` and `removed` by id, and `yours`
(rules the team wrote, kept as they were). `written: false` means the console has no rules for
this repository and none were synced before, so no file was created. Synced rules are headed by
their id (`r12`) and replaced by the next sync: they are changed in the console, not here.

### 3. Start from the console's settings — a new repository only

Only when `FILES` holds no `.cloudaeye.config` and `REPO` is known; otherwise skip this step.
Call `mcp__plugin_cloudaeye_cloudaeye__ultrareview_settings` with `repo`: `REPO`. Its `settings`
are what the CloudAEye console sets apart from the defaults, as this file's keys; `source` says
whose they are.

- `source: none` — say in one line that the console's settings could not be read, and why
  (`error`), and go on.
- Empty `settings` — say in one line that the console has ultrareview at its defaults, and go on.
- Otherwise print them as a short table, **Setting | Value**, under one line saying whose they
  are (*this repository's settings in the console* or *your account's default in the console*),
  and ask exactly: *Start `.cloudaeye.config` from these? (yes / no)*. On yes, `RS seed` with
  `answer` = the **whole** answer, unchanged, and apply `writes`. Say which settings were written
  (`set`) and any `problems`. On no, write nothing.

From here the file is what CloudAEye's commands read; the console is not read again.

### 4. Which directory

A directory argument answers this; otherwise, when `FILES` holds settings files outside the
root, name them, and ask exactly:

```text
Where should these settings apply?
  1. The whole repository (default)
  2. One directory and everything below it — type its path
```

Enter or `1` is the root: `DIR` is empty. A path is `DIR`, relative to `TOP`; check that it is a
directory with Glob (`<DIR>/*` under `TOP`) and, when nothing is there, say there is no such
directory and ask again. With the argument `rules`, go straight to step 6.

### 5. One section at a time

`RS show` with `directory` = `DIR`, and go through its `result.settings` section by section, in
this order (the LLM and Triage PRs only at the root — `show` leaves them out elsewhere):

| # | Section | Settings (key) |
|---|---|---|
| 1 | Ultrareview — checks | PR checklist (`ultrareview.checks.checklist`), Bugs (`ultrareview.checks.bugs`), Security (`ultrareview.checks.security`), AI slop score (`ultrareview.checks.slop`), Risk score (`ultrareview.checks.risk`), Architecture (`ultrareview.checks.architecture`), Control flow (`ultrareview.checks.control_flow`), Task check (`ultrareview.checks.task`) — true or false |
| 2 | Ultrareview — limits | Risk score (`ultrareview.limits.risk`), AI slop score (`ultrareview.limits.slop`) — 0 to 100; Review severity (`ultrareview.limits.severity`) — medium or low |
| 3 | Ultrareview — human review policy | Auto-assign human reviewer (`ultrareview.assign_reviewers`) — true or false; Max human reviewers to assign (`ultrareview.max_reviewers`) — 1, 2 or 3, 1 by default; Instructions (`ultrareview.instructions`) — one paragraph in plain words |
| 4 | Review | Severity floor (`review.severity_floor`) — all, critical, high, medium, low; Paths never reviewed (`review.skip`) |
| 5 | Review — LLM | LLM (`review.llm`) — CloudAEye or your own; Provider (`review.provider`) — your own only; Model (`review.model`) — one name; Model inversion (`review.invert_model`) — true or false; your own key goes in the plugin's settings or the console, never in this file |
| 6 | Control flow | Effort (`control_flow.effort`) — low, medium or high; Across repositories (`control_flow.cross_repo`) — true or false |
| 7 | Triage PRs | OKRs (`triage.okrs`) — text, or a file in the repository |

For each section print a short table — **Setting | Now | Options** — where *Now* is the
setting's `value` (a list one item a line); otherwise its `inherited` value followed by
*(from <inherited_from>)*; otherwise its `default`, followed by *(default)* unless it is
*none* or *CloudAEye's own check*, which stand alone — never a number for that check.
*Options* is the row's `options` joined with *or*. Under the table, one line of what the
section means:

1. *A check set to false is not run. With Bugs, Security, AI slop score or Risk score
   false, nothing is approved automatically.*
2. *Hard limits: a change above any of them is never approved automatically. Some
   findings always need a human too, such as a leaked secret or a Critical issue.*
3. *On a pull request that is not approved, ultrareview names human reviewers (true by
   default; with false it names nobody and a human must still look) — one, unless the
   instructions ask for more, and never more than the maximum (one by default, so an
   instruction asking for two needs a maximum of 2 or 3). The instructions are one
   paragraph in plain words, for example "Changes under `services/payments/` always need
   two humans." They can ask for more review, never less; team names are the ones in the
   Teams section of .OWNERS.md; a directory's instructions add to the root's.*
4. *The floor applies to /cloudaeye:inspect, /security and /review when you give no
   level; ultrareview ignores it. Paths never reviewed are relative to this directory
   and left out of the change before it is reviewed, before a commit only.*
5. *Which models review the code, for the review commands and ultrareview's review.
   CloudAEye uses CloudAEye's models; your own uses your account with a provider. The key
   never goes in this file: each developer can enter theirs in the plugin's settings (stored
   in their system's credential store), or the team saves one in the console (Settings → LLM
   → Bring your own LLM), which is used when no developer key is set. Model inversion: when AI
   authorship is detected, a different model family reviews the code; a Model or Provider
   set here wins over it. Left out, each uses the console's setting.*
6. *How much effort the control-flow map spends following calls, and whether it looks
   for callers in your other repositories.*
7. *The key results /cloudaeye:triage-prs weighs each pull request against.*

Then ask: *Change anything here? Reply in your own words ("risk 40, slop 50", "turn
off architecture"), "next" to keep it as it is, or "done" to finish.*

Turn the reply into one `RS` call for the section, with `directory` = `DIR`, then apply
`writes`:

- values → `RS set` with `args` = `["KEY=VALUE", …]` (several pairs at once);
- back to the default (or to what it inherits) → `RS set` with `args` = `["KEY=-"]`;
- the instructions → `RS set` with `args` = `["ultrareview.instructions=<the paragraph>"]`
  writes or replaces them, `RS add` with `args` = `["ultrareview.instructions", "<a sentence>"]`
  adds to the end, `RS clear` with `args` = `["ultrareview.instructions"]` takes them out;
- a path never reviewed → `RS add` with `args` = `["review.skip", "<path>"]`, one call each; to
  replace them all, `RS clear` with `args` = `["review.skip"]` first; to remove one, clear and
  add back the rest.

With **LLM: your own** written, say once: *Enter your key in the plugin's settings — run
`/plugin`, open CloudAEye and set **Your LLM API key** (kept in your system's credential store) —
or save one for the whole team in the console: https://console.cloudaeye.com/code-review/settings?tab=LLM
(Settings → LLM → Bring your own LLM).* Never write a key into `.cloudaeye.config`, and never
ask the user to paste one into this conversation.

Write only what the user asked for, in their words for instructions — never reword an
instruction into a stricter or looser one. An answer that is not one of the options comes
back as an error naming them: say so and ask again; never pick the nearest option. After the
call, print the section's new values from `result.values` in one line, and go to the next
section. "done" ends the questions: go to step 6.

### 6. Rules of your own

Ask: *Add a rule of your own? Say it in plain words, and the paths it applies to
if not everywhere under this directory — or "no".* For each one: `RS add-rule` with
`directory` = `DIR`, `heading` = a short title, `text` = the rule in their words, and `paths` =
the paths it applies to, comma-separated and relative to `DIR` (left out for all of it); then
apply `writes`.

### 7. What changed

Print:

- each file written (its `path`), and each setting changed, as *before → after*;
- the rules synced or added;
- which commands read what:
  - `/cloudaeye:ultrareview` — the checks, hard limits, the human review policy, the LLM settings (for its review), the rules, and the control-flow settings;
  - `/cloudaeye:inspect`, `/cloudaeye:security`, `/cloudaeye:review` — the severity floor, the LLM settings, the paths never reviewed and the rules;
  - `/cloudaeye:control-flow` — the effort and the search across repositories;
  - `/cloudaeye:triage-prs` — the OKRs.
- one line: *Commit `.cloudaeye.config` and `.cloudaeye.rules` so your team uses them
  too. Pull requests read them from the target branch, so they apply to pull requests
  once merged there.*

## Rules

- Write only `.cloudaeye.config` and `.cloudaeye.rules`, only what `repo_settings` answered in
  `writes`, and only under `TOP`. Never commit or push them yourself.
- Never change a setting the user did not ask about, and never put a secret, token or
  password in these files: they are committed. An LLM key belongs in the plugin's settings or
  the console. If the user pastes a key here anyway, write nothing, tell them where it goes, and
  say it is now in this conversation, so they may want to rotate it. Never print a key back.
- The limits are the user's own numbers. Never say how CloudAEye's scores are built
  or what its own limits are.
