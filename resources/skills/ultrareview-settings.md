# The team's settings in an ultrareview (read only when settings files apply)

The team's settings are `.cloudaeye.config` and `.cloudaeye.rules` files in the
repository (`/cloudaeye:config` writes them): one at the root, and any in a directory
cover that directory and below. Step 1 reads the ones that apply to this change's
files — from the working tree before a commit (the upload's `settings`), from the pull
request's **target branch** on a pull request (`SESSION.settings`), so a pull request
cannot change its own settings. Keep that JSON as `SETTINGS`. `error` means they could not be read:
say so in one line and run on CloudAEye's defaults. Say once, a line each:

- `applied` — the files that decided this run (*Using your settings from
  `.cloudaeye.config` and `services/payments/.cloudaeye.config`*);
- each of `problems` — a line a file could not read, whose default stands;
- `pending` (pull requests only) — *This pull request changes <files>; CloudAEye uses
  them once they are merged into <target>*;
- `fetched: false` — *<target> could not be fetched; read from your last copy of it*.

What they decide, as arguments of step 3's one call:

- **`SETTINGS.ultrareview`** — the checks, hard limits, `assign_reviewers`,
  `max_reviewers` and the instructions (a paragraph a settings file) — goes whole,
  as it is, as `policy`. Leave `policy` out when it is absent. The server reads
  `policy.checks` itself: a check set to `false` is not run, and Bugs and Security
  pick the review's half (with both false the AI slop score runs its own pass). Never
  skip a pass or choose a profile yourself. Bugs, Security, AI slop and risk are what
  an approval rests on: with any of them false, the verdict is a human review.
- **`SETTINGS.review`'s LLM settings** — for the review only, each when the user gave
  no option for it: `model` as `review_model`, `provider` as `model_provider` (present
  only with `llm` set to `your own`), `invert_model` as `invert_model`. Say once which
  came from the settings. An option the user typed always wins.
- **Your own LLM key** comes from the plugin's setting *Your LLM API key*, which Claude Code keeps in
  your system's credential store and sends to CloudAEye itself: `SESSION.llm_key` is `plugin_setting`
  when it did, and `SESSION.llm_key_problem` says when the value was not a key (say so). Pass
  `llm_key: true` when `SESSION.llm_key` is `plugin_setting`, or `SETTINGS.review.api_key.sent` is
  `true` (a key a team wrote in the file), and `model_provider` is openai, anthropic or deepseek.
  Otherwise pass nothing: the key saved in the CloudAEye console is used. Never read, print or repeat
  a key, and never pass one to a tool.
- **`SETTINGS.rules`** — the team's review rules — go as `rules`, each `{id, text,
  paths}` as given, when there are any.
- **Paths never reviewed** — step 1 leaves them out of the uploaded change, before a
  commit only; on a pull request the server reads the whole pull request. The scope
  label in step 3 says so.
- **`SETTINGS.control_flow`** — `effort` as `depth` (`low` 1, `medium` 2, `high` 3)
  and `cross_repo` as it is.
- **`SETTINGS.review.severity_floor` is not used here**: the AI slop score cannot
  reuse a review run with a floor, and would pay for its own. Pass `min_severity`
  only when the user typed a severity option.

In the step-by-step flow, `${CLAUDE_PLUGIN_ROOT}/resources/skills/ultrareview-steps.md` says
which step takes each of these.

## In the report

**Your settings** — when the result carries `settings`: one line, *Decided with your
settings* (the files in `SETTINGS.applied`, and *as on <target>* on a pull request)*:*
the hard limits (risk *n*/100, AI slop *n*/100, review severity), the most human
reviewers to assign (`max_reviewers`, or *assigning turned off* when `settings` has
`assign_reviewers: false`) and the checks turned off, as `settings` gives them. Under it, each of `instructions` — the instruction in quotes, *applied* or *not
applied*, and its `why` — then, when the result carries `reviewers_capped`, *an
instruction asked for <asked> reviewers; your settings assign at most <max>*, and each
of `policy_problems` (a setting that was left out). Never print this block when there
were no settings.
