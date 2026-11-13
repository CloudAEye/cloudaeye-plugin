# CloudAEye settings

<!-- A setting inside comment marks is not read. To change one, remove the marks around its
     line, or run /cloudaeye:config. The comment after a setting lists its options.
     This file covers its own directory and everything below it. A .cloudaeye.config further
     down wins over it, setting by setting. When a change touches files under different
     settings, it gets whichever asks for more review.
     A setting placed here overrides the same setting in CloudAEye's console settings.
     On a pull request, CloudAEye reads it from the target branch, so a pull request cannot
     change its own settings. -->


## Ultrareview

### Checks
<!-- A check set to false is not run. With Bugs, Security, AI slop score or Risk score false,
     nothing is approved automatically. -->
<!-- - PR checklist: true -->             <!-- true | false. Pull requests only -->
<!-- - Bugs: true -->                     <!-- true | false -->
<!-- - Security: true -->                 <!-- true | false. Includes leaked secrets -->
<!-- - AI slop score: true -->            <!-- true | false -->
<!-- - Risk score: true -->               <!-- true | false -->
<!-- - Architecture: true -->             <!-- true | false -->
<!-- - Control flow: true -->             <!-- true | false -->
<!-- - Task check: true -->               <!-- true | false. Runs when a task is given -->

### Limits
<!-- Hard limits: a change above any of these is never approved automatically. Left out,
     CloudAEye's own check applies. -->
<!-- - Risk score: 40/100 -->             <!-- 0-100 -->
<!-- - AI slop score: 50/100 -->          <!-- 0-100 -->
<!-- - Review severity: medium -->        <!-- medium | low. The worst finding a change may have -->

### Human review policy
<!-- Pull requests only.
     Auto-assign human reviewer: when CloudAEye does not approve a change automatically, it
     names human reviewers for it on the pull request. With false it names nobody, and a human
     must still look.
     Max human reviewers to assign: the most people named, one by default. One is named unless
     the instructions ask for more, and never more than this.
     Instructions: plain words, as long as you like, carried on indented lines under the label.
     They can ask for more review, never less. -->
<!-- - Auto-assign human reviewer: true -->       <!-- true | false. Default true -->
<!-- - Max human reviewers to assign: 1 -->       <!-- 1 | 2 | 3. Default 1 -->
<!-- - Instructions: Changes under `services/payments/` always need two humans. Pull requests
       from the Platform team need one reviewer from outside the team. -->


## Review
<!-- /cloudaeye:inspect, /cloudaeye:security, /cloudaeye:review -->

### Severity floor
<!-- Report only findings at or above this. Ultrareview ignores it. -->
<!-- - Severity floor: all -->            <!-- all | critical | high | medium | low. Default all -->

### LLM
<!-- Which models review the code, for the review commands and ultrareview's review; the other
     commands use the models set in the console settings. Read from the repository's top-level
     file only. Left out, each setting follows the console settings. A --model, --model-provider
     or --invert-model option on a command wins for that run.
     API key: with your own LLM and Provider openai, anthropic or deepseek. Write the name of an
     environment variable that holds the key, like $OPENAI_API_KEY, so the key stays out of the
     repository; a key written here can be read by anyone who can read the repository. Left out,
     the key saved in the console settings is used (Settings > LLM > Bring your own LLM). -->
<!-- - LLM: CloudAEye -->                 <!-- CloudAEye | your own -->
<!-- - Provider: openai -->               <!-- your own only: openai | anthropic | azure | aws_bedrock | gcp_vertex | groq | deepseek -->
<!-- - Model: gpt-6.1-terra -->           <!-- CloudAEye: a model the console offers. Your own: the provider's exact model name -->
<!-- - Model inversion: true -->          <!-- true | false. When AI authorship is detected, a different model family reviews the code. A Model or Provider set here wins over it -->
<!-- - API key: $OPENAI_API_KEY -->       <!-- your own only: an environment variable that holds the key, or the key -->

### Paths never reviewed
<!-- Before a commit only. One path or pattern per line, relative to this file's directory. -->
<!-- - Skip: `**/generated/**` -->


## Control flow
<!-- /cloudaeye:control-flow. Ultrareview uses these too. -->
<!-- - Effort: medium -->                 <!-- low | medium | high. Default medium. How far the map follows calls -->
<!-- - Across repositories: true -->      <!-- true | false. Default true -->


## Triage PRs
<!-- /cloudaeye:triage-prs. Read from the repository's top-level file only. -->
<!-- - OKRs: `docs/okrs-q4.md` -->        <!-- your team's key results in plain words, or a file that holds them -->
