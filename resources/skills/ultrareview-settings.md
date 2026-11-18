# The team's settings in an ultrareview (printed only when settings files apply)

The team's settings are `.cloudaeye.config` and `.cloudaeye.rules` files in the
repository (`/cloudaeye:config` writes them): one at the root, and any in a directory
cover that directory and below. Step 1 reads the ones that apply to this change's
files — from the working tree before a commit, from the pull request's **target
branch** on a pull request, so a pull request cannot change its own settings — and
prints them as JSON after `settings:`. Keep that JSON as `SETTINGS`. With no files it
holds only empty `rules` and changes nothing. `error` means they could not be read:
say so in one line and run on CloudAEye's defaults. Say once, a line each:

- `applied` — the files that decided this run (*Using your settings from
  `.cloudaeye.config` and `services/payments/.cloudaeye.config`*);
- each of `problems` — a line a file could not read, whose default stands;
- `pending` (pull requests only) — *This pull request changes <files>; CloudAEye uses
  them once they are merged into <target>*;
- `fetched: false` — *<target> could not be fetched; read from your last copy of it*.

What they decide:

- **`SETTINGS.ultrareview.checks`** — a check set to `false` is not run: skip its
  step below. Bugs, Security, AI slop and risk are what an approval rests on: with
  any of them false, the verdict is a human review. Bugs and Security are the two
  halves of the review in step 2, and pick its profile: both true (or unset)
  `"review"`; Bugs false `"security"`; Security false `"bugs"`; both false, skip
  steps 2 and 9 (the AI slop score runs its own pass).
- **`SETTINGS.ultrareview`** — the checks, hard limits, `assign_reviewers`,
  `max_reviewers` and the instructions (a paragraph a settings file) — goes whole,
  as it is, as `policy` to `review_summary` (steps 10 and 12). Leave `policy` out
  when it is absent.
- **`SETTINGS.review`'s LLM settings** — for the review in step 2 only, each when
  the user gave no option for it: `model` as `review_model`, `provider` as
  `model_provider` (present only with `llm` set to `your own`), `invert_model` as
  `invert_model`. Say once which came from the settings. An option the user typed
  always wins. **An API key** in the settings is sent to CloudAEye by step 1 itself:
  `SETTINGS.review.api_key` says only where it comes from, whether it was found and
  whether it was `sent`. Never read, print or repeat the key, and never pass it to a tool.
- **`SETTINGS.rules`** — the team's review rules — go as `rules` to the review
  (step 2) when there are any.
- **Paths never reviewed** — step 1 leaves them out of the uploaded change, before a
  commit only; on a pull request the server reads the whole pull request.
- **`SETTINGS.control_flow`** — for step 7: `effort` as `depth` (`low` 1, `medium` 2,
  `high` 3) and `cross_repo` as it is.
- **`SETTINGS.review.severity_floor` is not used here**: the AI slop score cannot
  reuse a review run with a floor, and would pay for its own.

## In the report

**Your settings** — when step 10 returned `settings`: one line, *Decided with your
settings* (the files in `SETTINGS.applied`, and *as on <target>* on a pull request)*:*
the hard limits (risk *n*/100, AI slop *n*/100, review severity), the most human
reviewers to assign (`max_reviewers`, or *assigning turned off* when `settings` has
`assign_reviewers: false`) and the checks turned off, as `settings` gives them. Under it, each of `instructions` — the instruction in quotes, *applied* or *not
applied*, and its `why` — then, when step 10 returned `reviewers_capped`, *an
instruction asked for <asked> reviewers; your settings assign at most <max>*, and each
of `policy_problems` (a setting that was left out). Never print this block when there
were no settings.
