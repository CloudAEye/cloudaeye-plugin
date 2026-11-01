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
<!-- - Review: on --> <!-- bugs and security -->
<!-- - AI slop score: on -->
<!-- - Risk score: on -->
<!-- - Architecture: on -->
<!-- - Control flow: on -->
<!-- - Task check: on -->

### Limits
<!-- Hard limits: a change above any of these is never approved automatically. -->
<!-- - Risk score: 40/100 -->
<!-- - AI slop score: 50/100 -->
<!-- - Review severity: medium | low -->

### Human reviewers
<!-- The most humans to assign when a change is not approved: 1 | 2 | 3.
     One is assigned unless your ultrareview instructions ask for more. -->
<!-- - Max human reviewers to assign: 2 -->

### Ultrareview instructions
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
<!-- /cloudaeye:control-flow. Ultrareview uses these too.
     Effort: low | medium | high, how far the map follows calls.
     Across repositories: yes | no. -->
<!-- - Effort: medium -->
<!-- - Across repositories: yes -->


## Triage PRs
<!-- /cloudaeye:triage-prs. Read from the repository's top-level file only.
     OKRs: your team's key results, or a file that holds them. -->
<!-- - OKRs: `docs/okrs-q4.md` -->
