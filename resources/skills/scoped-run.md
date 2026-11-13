# A run scoped to a path (only when the user named a file or directory)

Add `--scope '<the path>'` to the skill's first command (`cae start … --scope '<the path>'`) and to
the upload (`cae upload '<SESSION as JSON>' … --scope '<the path>'`). The scope is applied where the
diff is made, so only that subtree is ever uploaded: a directory covers everything beneath it, a
file just that file.

- `diff_bytes=0` with a scope: nothing has changed under that path. Say so **naming the path**, and
  stop. Never widen to the whole change: they asked about one place.
- `cloudaeye_error=scope_outside_repo`: the path escaped the repository (`..`, absolute, or `~`).
  Report it and stop.
- `diff_files` below `total_files`: **say what was left out**, with both numbers — "covered 2 of 7
  changed files (src/auth/)". A result over one path reads exactly like a result over the whole
  change, and nothing else in the output says which it is: an `approve`, a score or a verdict here
  means *for that path*.
- **A scoped run is blind outside its scope.** The cross-file checks see only files in the diff: a
  caller broken by a changed signature, the other copy of duplicated code, or the definition a call
  relies on will not be found in a file the path left out. Say so in one line when files were left
  out.
- Pass `context: {"scope_path": "<the path>"}` to the analysis tool. It filters nothing — the diff
  is already narrowed — but it is what makes the answer say what it covered. The answer echoes
  `scope`; keep it in what you report.
