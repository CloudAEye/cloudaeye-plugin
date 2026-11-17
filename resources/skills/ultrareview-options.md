# Ultrareview's options (only when the user typed `task:` or a flag)

Read them in this order, before step 1. Each becomes an argument of step 3's one call (in the
step-by-step flow, `cae guide ultrareview-steps` says which step takes it).

1. **`task:`** — everything after `task:` to the end of the input is the task,
   verbatim. Route it as `/cloudaeye:check-task` does: GitHub issue URL →
   `task_source="github-issue"`, the URL as `task_description`; Jira keys
   (`\b[A-Z][A-Z0-9]+-\d+\b`, brackets stripped, comma-separated) →
   `task_source="jira"`; anything else → `task_source="user-text"`, the text
   verbatim. Never summarise it. Pass `task_description` and `task_source` on the
   working tree or a path only: on a pull request the task check does not run.
2. **Model options** — `--model` → `review_model`, `--model-provider` →
   `model_provider`, `--invert-model` → `invert_model` (boolean `true` or
   `false`, never a string). They apply to **the review only**. One the user
   did not give comes from the repository's LLM settings when they set it (see
   **Your settings**), and is omitted otherwise. Reject a missing value, an
   unknown flag or another inversion value before initializing anything.
3. **Severity floor** — `--critical`, `--high`, `--medium` or `--low` →
   `min_severity` with the dashes stripped, for **the review only**. When one is
   given, say once: *the floor narrows the review, so the AI slop score cannot
   reuse it and runs its own pass.* An unrecognised value is refused by the
   server; report it rather than retrying without the floor.
