# 26-agent-adaptive-trigger

**Status: stub — placeholder. Not implemented yet.**

An Agent Management version of
[16-adaptive-triggers](../16-adaptive-triggers/). Example 16 watches a latency
metric and switches a highlight flag from `green` to `none`. This example will
switch a briefing from its primary model to a **safer model** when a metric
says the primary one is in trouble.

Nothing else is settled. Do not build the app from this file alone.

Keywords: **adaptive triggers** · **Agent Management** · **completion config** ·
**custom numeric metric** · **safer model**

Docs: [Adaptive triggers](https://launchdarkly.com/docs/home/flags/triggers) ·
[AI Configs](https://launchdarkly.com/docs/home/ai-configs)

## What we will build

A running briefing, the same shape as
[201-agent-completion-config](../../20-agent-management/201-agent-completion-config/).
The screen shows which model produced the draft. When the metric crosses the
threshold and stays there for the alert window, the next draft comes from the
safer model. The drawer records the switch the way example 16 records
`green → none`.

The grid highlight trigger stays in example 16. This one is the model.

## Ideas for the build

These are options, not a design. Pick one when `application.md` is written.
Confirm the current product docs first: example 16's adaptive trigger is
attached to a **feature flag**. It is not obvious that the same trigger can
attach to an AI Config.

1. **Two variations on one completion config.** Primary model, and a safer
   one (smaller, cheaper, or a tighter system prompt). The lab shows the
   model name on each draft. This is the cleanest story if a trigger or a
   guarded rollback can retarget the config itself.
2. **A flag in front of the config.** String flag `agent-model-safety` with
   variations `primary` and `safe`. The adaptive trigger lives on that flag,
   exactly as example 16's trigger lives on the highlight flag. The app reads
   the flag and asks the completion config for the matching variation. Use
   this if triggers still only attach to flags.
3. **What the metric could be.** Generation latency, matching example 16's
   numeric metric. An error rate on the model call. Or the judge fail rate
   already produced by
   [204-agent-judges](../../20-agent-management/204-agent-judges/). Latency is
   the easiest to demo with a slider. A judge score is the one that matches
   "the model got worse," and it needs a judge in the loop.
4. **What "safer" could mean.** A smaller local model instead of a large one.
   A lower temperature. A system prompt that refuses to speculate. Show the
   difference on screen, or the switch is invisible.

## Do not

- Copy example 16's highlight flag into this folder.
- Invent a trigger API that the docs do not describe. If the trigger cannot
  target an AI Config, say so in `application.md` and use the flag in idea 2.
- Roll this into [20-capstone-1](../../20-agent-management/20-capstone-1/).

## When implementing

1. Read the adaptive-trigger docs and decide idea 1 or idea 2.
2. Write `application.md`: config key or flag key, both model variations,
   metric key, threshold, and alert window.
3. One language is enough for the first pass. Python matches example 16's
   sibling web apps and 201.
