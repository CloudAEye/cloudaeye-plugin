# A pull request (only when the user gave a PR number)

The server fetches the pull request's diff from GitHub itself: nothing is uploaded, and no diff
leaves the machine. Follow the skill's steps with these differences.

1. The first command is `cae start --pr`, with no other flag. Call `start_session` with the fields
   of its first line **and `pr_number`**: the digits the user gave, any `#` stripped.
2. `status: error`: print the `error` as written and stop. It is the eligibility refusal — the pull
   request must be **open** (drafts are fine), merge into the repository's **integrated branch**,
   **not come from a fork**, and change **at most 50 files** — and each refusal names a different
   thing to do. Never paraphrase it, and never fall back to the working tree: that is a different
   change, and would read as an answer to the question the user asked. **With `demo: true` beside it, it is not a
   refusal:** it is the report CloudAEye already posted on a public demo repository's pull request.
   Print it exactly as written and nothing else: no line about a refusal, the session or what did
   not run. Its last line, the link to the comment, is where the run ends.
3. On success `SESSION.pull_request` carries the number, title, `draft`, `base`, `head`, `head_sha`
   and `changed_files`. Say which pull request this is, and say so when it is a draft.
4. **Skip the upload.** "The same change as last time" is `SESSION.diff_unchanged`.
5. A command that reads the team's settings (review, inspect, security) reads them as the target
   branch has them, so a pull request cannot change its own:
   `cae pr-settings '<SESSION as JSON>' --review --guide review-settings`.
6. A command that takes an intent: you did not write this change, so do not pretend to. Use the pull
   request's own title and description — the server already put them on the session — and say in
   one line that the intent is the author's stated purpose. Do not open the changed files to write a
   better one.
7. A pull-request run is its own session, separate from the working-tree one for the same
   repository, so it never overwrites unfinished local work. Running the same pull request again
   resumes it; new commits are fetched again, and with none nothing is re-derived.
8. `/cloudaeye:implement` does not work on a pull-request run: its plans describe edits to a
   working tree, and this source lives on GitHub. If the user wants to fix what was found, they
   check the branch out and run the command locally. Say that rather than offering a plan.
