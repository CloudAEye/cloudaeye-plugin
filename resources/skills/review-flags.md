# Severity and model options (only when the user typed one)

## A severity floor: `--critical`, `--high`, `--medium`, `--low`

Pass it as `min_severity`, the dashes stripped. **It is a floor, not an exact match**: `--high`
reports high *and* critical. It reaches the scan as well as the final filter, so a floored run
costs less rather than merely showing less. The server refuses a value it does not know: report
that error, and never retry without the flag — reviewing everything when the user asked for
critical only is a failure they cannot see.

The answer then carries `min_severity`, and `held_back` counts what sat below the floor. **Report
both.** "No findings" and "no findings at or above critical, and four below it" are different
answers. A flag always wins over a floor in the team's settings.

## Model options (this run only; they never change saved settings)

| Flag | Tool argument | Value |
|---|---|---|
| `--model` | `review_model` | A model family (`gpt`) or an exact model ID |
| `--model-provider` | `model_provider` | The hosting provider (`azure`) |
| `--invert-model` | `invert_model` | Boolean `true` or `false`, never a string |

They are top-level tool arguments, not fields inside `context`. Reject a missing value, an unknown
flag, or an inversion value other than `true` or `false` **before starting a session**. An option
the user did not give comes from the team's settings when they set it, and is left out otherwise;
an omitted `invert_model` uses the account's saved setting, never a default of yours. An explicit
model or provider wins over inversion. Pass what was given; the server resolves models, providers
and credentials. Report a selection error and stop: never retry with another model, and never drop
an option silently.
