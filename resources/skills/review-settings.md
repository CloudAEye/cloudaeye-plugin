# The team's settings (read only when settings files apply to this change)

`SETTINGS` is what the `.cloudaeye.config` and `.cloudaeye.rules` files that cover this change's
files say: the upload's `settings` before a commit (from your working tree), `SESSION.settings` on a
pull request (from its target branch). `error` means run without them: say so in one line. Print
each of `problems` once, and on a pull request `pending` (*this pull request changes <files>; they
apply once merged*). What they change in the review call:

- **`SETTINGS.review.severity_floor`** is `min_severity` when the user gave no severity flag (`all`
  means none). Say once that the floor came from your settings. A flag always wins.
- **`SETTINGS.review`'s LLM settings**, each when the user gave no option for it: `model` as
  `review_model`, `provider` as `model_provider` (present only with `llm` set to `your own`),
  `invert_model` as `invert_model`. Say once which came from your settings.
- **Your own LLM key** comes from the plugin's setting *Your LLM API key*, which Claude Code keeps in
  your system's credential store and sends to CloudAEye itself: `SESSION.llm_key` is `plugin_setting`
  when it did, and `SESSION.llm_key_problem` says when the value was not a key (say so). Pass
  `llm_key: true` when `SESSION.llm_key` is `plugin_setting`, or `SETTINGS.review.api_key.sent` is
  `true` (a key a team wrote in the file), and `model_provider` is openai, anthropic or deepseek.
  Otherwise pass nothing: the key saved in the CloudAEye console is used. Never read, print or repeat
  a key, and never pass one to a tool.
- **`SETTINGS.rules`** are the team's review rules: pass them as `rules`, each `{id, text, paths}`
  as given. `rules_problems` in the answer names any left out; say so.
- **Paths never reviewed** are left out of the uploaded change (before a commit only; on a pull
  request the server reads the whole pull request). `skipped_by_settings` above `0` in the upload's
  answer is how many changed files that was: say so, naming the patterns, and set
  `context.scope_path` to `"<the path, or the whole change> except <the patterns, comma-separated>"`.
