# An ultrareview of a pull request (only when the user gave a PR number)

The server fetches the pull request's diff from GitHub itself: nothing is uploaded. Follow the
skill's steps with what is below; the step numbers are the skill's own.

## Before step 1

In pull-request mode, say once under the tree: *the report is posted on the
pull request as one comment, as the other commands post their cards, and
edited in place when you run this again; the PR checklist keeps its own
comment, as `/cloudaeye:check` always does.*

In the tree, **PR checklist** runs, **Task check** is *skipped: uncommitted changes only*, and
**Human review** runs only if a human review is required.

## Step 1

The command is `cae start --pr`, with no other flag. Call `start_session` with every field of its
first line, unchanged, **and `pr_number`** (the digits, `#` stripped), and skip the upload. On `status: error`,
print the `error` as written and stop: it is the eligibility refusal (closed, wrong base branch,
fork, over 50 files), and each names a different thing to do. Never review the working tree
instead. **`demo: true` beside the `error` is not a refusal:** it is the report CloudAEye already posted on a
public demo repository's pull request. Print the `error` exactly as written and nothing else: no line
about a refusal, the session, checks that did not run or what was posted. Its last line, the link to
the comment, is where the run ends. On success, say which pull request this is (number, title, head SHA) and whether it is a
draft. Then read the settings as the target branch has them, so a pull request cannot change its
own: `cae pr-settings '<SESSION as JSON>' --review --guide ultrareview-settings`.

The same change as last time is `SESSION.diff_unchanged`. A new change's intent is the pull
request's own title and description; say in one line that it is the author's stated purpose.

## Step 3

Pass `post: true`: the PR number is the request to post, so never ask. Pass no `author` (the
author is the pull request's) and no `task_description` or `task_source` (the task check is for
uncommitted changes only). The rest of step 3 stands.

On a pull request the server also does what this skill used to do in steps of its own: it starts
the PR checklist first and collects it later, which posts its own comment and supplies risk's
unit-test coverage; when a human review is required and assigning is not turned off, it suggests
reviewers (and requests nobody); and it posts the whole report as one comment — or edits the one
an earlier run posted — whatever the verdict.

In the step-by-step flow (`cae guide ultrareview-steps`), that guide has the pull-request steps,
and its report section says where the reviewers and the *Posted* line come from.

## In the report

Under **Suggested reviewers**, by `steps.reviewers`:

- `suggested`: the reviewers line **exactly as the result's `card` has it** — the
  `**Suggested reviewers:**` line, or, when a review was already requested, the
  `**Review requested from:**` line with its `**Also suggested:**` line. It names each person as
  `name` (`login`) — `role`, never @-mentioned (a mention notifies them), and says when fewer were
  found than asked for. Under a `**Suggested reviewers:**` line add one line: *a suggestion — no
  review has been requested; `/cloudaeye:assign-reviewer #<n>` asks for them when you want it.*
  How they were suggested is in the saved report and the pull-request comment. When `card`
  carries no such line, write *Suggested reviewers: named in the full report and in the pull
  request comment.* Never name anyone the `card` does not.
- `none could be suggested`: *Suggested reviewers: none could be suggested.*
- Anything else: *Suggested reviewers: none suggested —* and the value as given.

**Posted.** In pull-request mode, one line under *What to do next* from the result's
`posted`: `ok` → *Posted on the pull request:* the link (`url`), saying
*updated in place* when `edited` is true and *unchanged* when `unchanged` is;
`failed` or `unavailable` → *Not posted on the pull request:* and its `note`;
`unknown` → that delivery could not be confirmed and it will not be retried
automatically — check the pull request before running again. When nothing was
posted because the run did not finish — the result has `status: "error"`, or the
job was still pending at its deadline — say so in this line: *Not posted on the
pull request: the run did not finish*, and why. Never leave a pull-request run
without this line.

After the report line, end with the link `[<repo>#<pr_number>](<pr_url>)`, where the report now
sits (`<pr_url>` is `https://github.com/<repo>/pull/<pr_number>`).
