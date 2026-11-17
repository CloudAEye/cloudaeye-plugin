# No target branch to diff against (only when the skill's upload could not use one)

`SESSION.target_branch` is empty (the repository is not connected to CloudAEye, or its integrated
branch could not be read), or the upload command stopped at a `git` error before `curl` ran (most often
because `origin/<TARGET>` is not known in this clone). Upload against your last commit instead: the
same command without the fetch, with `HEAD` as the baseline, and the same settings parts and path
as the skill's command:

```bash
mkdir -p .cloudaeye && echo '*' | tee .cloudaeye/.gitignore && printf 'url = "%s"\nheader = "X-Upload-Token:%s"\n' '<UPLOAD_URL>' '<UPLOAD_TOKEN>' | tee .cloudaeye/upload.curl && git rev-parse --git-path index | xargs -I{} cp -p {} .cloudaeye/index && export GIT_INDEX_FILE=.cloudaeye/index && git add -N . && git diff HEAD --output=.cloudaeye/session.diff -- . && git rev-parse HEAD | curl -sS --fail-with-body -K .cloudaeye/upload.curl -F 'base_sha=<-' -F 'file=@.cloudaeye/session.diff'
```

Read its answer as the skill says. This run is **degraded**: only the uncommitted edits are in the
diff, and work already committed on this branch is not. Say so. If `SESSION` carries
`setup_required`, report its `reason` and `remedy` as written; never quote `target_branch_error`,
which names an internal record.

If this command stops with an error too, report the last lines it printed and stop: this is
not a Git repository with a commit yet, or Git is older than 2.30.
