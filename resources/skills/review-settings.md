# The team's settings (printed only when settings files apply to this change)

The JSON above is `SETTINGS`: the `.cloudaeye.config` and `.cloudaeye.rules` files that cover this
change's files (`/cloudaeye:config` writes them), read from the working tree before a commit and
from the target branch on a pull request. `error` means run without them: say so in one line. Print
each of `problems` once, and on a pull request `pending` (*this pull request changes <files>; they
apply once merged*). What they change in the review call:

- **`SETTINGS.review.severity_floor`** is `min_severity` when the user gave no severity flag (`all`
  means none). Say once that the floor came from your settings. A flag always wins.
- **`SETTINGS.review`'s LLM settings**, each when the user gave no option for it: `model` as
  `review_model`, `provider` as `model_provider` (present only with `llm` set to `your own`),
  `invert_model` as `invert_model`. Say once which came from your settings.
- **An API key** in the settings is sent to CloudAEye by the upload step itself (on a pull request,
  by the settings step). `SETTINGS.review.api_key` says only where it comes from, whether it was
  found and whether it was `sent`. Pass `llm_key: true` only when `sent` is `true` and
  `model_provider` is the settings' provider. Never read, print or repeat the key, and never pass it
  to a tool.
- **`SETTINGS.rules`** are the team's review rules: pass them as `rules`, each `{id, text, paths}`
  as given. `rules_problems` in the answer names any left out; say so.
- **Paths never reviewed** are left out of the uploaded change (before a commit only; on a pull
  request the server reads the whole pull request). `skipped_by_settings` above `0` on the summary
  line is how many changed files that was: say so, naming the patterns, and set
  `context.scope_path` to `"<the path, or the whole change> except <the patterns, comma-separated>"`.
