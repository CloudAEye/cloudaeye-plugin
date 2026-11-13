# Review rules

<!-- Rules CloudAEye's review follows, in plain words: a heading, then the rule.
     A rule covers this file's directory and everything below it. "Applies to" narrows it to
     paths, relative to this directory.
     A heading that is an id (r12) is one of your organisation's rules, synced into the
     top-level file by /cloudaeye:config; change those in the console. Your own rules have no
     id, and syncing never touches them. -->

<!--
## No request bodies in logs
Never log a request or response body; log its size and the route instead.
- Applies to: `src/api/`
-->
