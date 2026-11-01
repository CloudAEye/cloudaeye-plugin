# CloudAEye settings

<!-- A setting inside comment marks is not read. To change one, remove the marks around its
     line, or run /cloudaeye:config.
     This file covers its own directory and everything below it. A .cloudaeye.config further
     down wins over it, setting by setting. When a change touches files under different
     settings, it gets whichever asks for more review.
     Commit it. On a pull request, CloudAEye reads it from the target branch, so a pull request
     cannot change its own settings. Every command posts its result on the pull request. -->


## Ultrareview

### Checks
<!-- on | off. A check that is off is not run. With Review, AI slop score or Risk score off,
     nothing is approved automatically. -->
<!-- - PR checklist: on -->
<!-- - Review (bugs and security): on -->
<!-- - AI slop score: on -->
<!-- - Risk score: on -->
<!-- - Architecture: on -->
<!-- - Control flow: on -->
<!-- - Task check: on -->

### Limits
<!-- Highest values CloudAEye may still approve on its own. -->
<!-- - Risk score: 40/100 -->
<!-- - AI slop score: 50/100 -->
<!-- - Review severity: medium | low -->

### Reviewers
<!-- Humans to ask for when a change is not approved: 1 | 2 | 3 -->
<!-- - Reviewers: 1 -->

### Instructions
<!-- Anything else, in plain words. Can ask for more review, never less. -->
<!-- - Pull requests from the Platform team need two humans: one from the team, one from outside it. -->
<!-- - Changes under `services/payments/` always need two humans. -->
<!-- - Always ask for one human, even when CloudAEye approves. -->


## Review
<!-- /cloudaeye:inspect, /cloudaeye:security, /cloudaeye:review -->

### Severity floor
<!-- Report only findings at or above: all | critical | high | medium | low.
     Ultrareview ignores this. -->
<!-- - Severity floor: all -->

### Paths never reviewed
<!-- Before a commit only. One path or pattern per line, relative to this file's directory. -->
<!-- - Skip: `**/generated/**` -->


## Control flow
<!-- /cloudaeye:control-flow. Ultrareview uses these too. -->
<!-- Depth: 2 | 1 | 3.  Across repositories: yes | no -->
<!-- - Depth: 2 -->
<!-- - Across repositories: yes -->


## Triage PRs
<!-- /cloudaeye:triage-prs. Read from the repository's top-level file only. -->
<!-- OKRs: your team's key results, or a file that holds them. -->
<!-- - OKRs: `docs/okrs-q4.md` -->
<!-- Show: how many pull requests to list. Label without asking: no | yes
     (a repository not labelled yet takes 3 to 8 AI calls, once). -->
<!-- - Show: 15 -->
<!-- - Label without asking: no -->
