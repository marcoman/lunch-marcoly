# 17-scheduled-changes application specification

Baseline login, grid, positions, and keyboard controls come from
[00-reference-code/application.md](../../00-reference-code/application.md).

## Overview

Teach LaunchDarkly **scheduled flag changes** with one visible event. The app
starts with an `X`-only selection and schedules the dedicated flag to turn on
after a selected delay. LaunchDarkly owns the clock; the browser only polls the
server SDK evaluation.

Keywords: **scheduled changes** · **feature flags** · **semantic patch** ·
**contexts**

Docs: [Scheduled flag changes](https://launchdarkly.com/docs/home/flags/scheduled-changes) ·
[Scheduled changes API](https://launchdarkly.com/docs/api/scheduled-changes)

Scheduled flag changes are a LaunchDarkly **Enterprise** feature.

## The aha

Choose one minute and start. The selected cell immediately returns to `X`
because the lab resets the flag off. The elapsed clock advances, but it does
not control the UI. Around the scheduled wall time, LaunchDarkly executes
`turnFlagOn`; the next SDK evaluation becomes `green`.

## Flag

| Attribute | Value |
|-----------|-------|
| **Name** | `Enable: grid selection highlight (scheduled)` |
| **Key** | `enable-grid-selection-highlight-sched` |
| **Variation type** | string |
| **Variations** | `none`, `green` |
| **Off variation** | `none` |
| **On fallthrough** | `green` |
| **Initial state** | **Off** |
| **SDK default** | `none` |
| **Tags** | `grid-navigator`, `enable`, `ui`, `string`, `scheduled-changes` |

## Schedule control

1. Offer **1, 2, 5, and 10 minute** delays; one minute is the minimum.
2. On **Start scheduled change**, delete all pending scheduled changes for this
   dedicated flag and environment.
3. Immediately turn the flag off so repeat demonstrations have a visible
   before state.
4. Create one scheduled change with the selected future `executionDate` and a
   `turnFlagOn` semantic instruction.
5. Show elapsed time from the start and the scheduled wall time. Do **not** show
   a countdown or flip the UI with a local timer.
6. Re-evaluate the flag every few seconds. Small API/SDK delivery differences
   from the selected delay are expected.
7. Record the elapsed time at which `green` first appears and show it next to
   the scheduled time, so the observed lag is visible.

Starting while a schedule is pending **replaces** it.

## Stop control

One button covers both states. Its label reads **Stop schedule** while a change
is pending and **Turn flag off** once the change has been applied. Either way
it performs both actions: delete every pending scheduled change and turn the
flag off. Cancelling alone would leave an already-executed change on, and
turning off alone would let a pending change flip it back on later.

The elapsed clock **holds its last value** after stopping. Starting a new
schedule resets it.

## Timing explanation

The lesson must state why the highlight can appear well after the selected
delay — a one-minute schedule commonly turns green around 1:30. LaunchDarkly
executes close to the execution date rather than exactly on it, the change then
has to reach the server SDK stream, and the page re-evaluates only every two
seconds.

## Runtime configuration

SDK evaluation needs `LD_SDK_KEY`. Schedule controls also need
`LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY`. Never send
the token to the browser.

## Out of scope

Progressive percentage stages, experiments, guarded rollouts, multiple
scheduled instructions, and client-side SDK evaluation.
