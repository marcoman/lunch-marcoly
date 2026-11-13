# playgrounds

**Status: stub — not implemented yet. Unnumbered.**

Agent Management **playgrounds**: try prompt and model variations on the
existing stock-picker configs, score the drafts, and leave production alone.

This stays in [20-agent-management](../README.md). A playground is a sandbox
for the equity briefing, not a new product. [70-model-demos](../../70-model-demos/)
is for apps that are not that briefing. **201–209** are already assigned, so
this folder does not take **210**.

Keywords: **playgrounds** · **Agent Management** · **offline evaluations** ·
**completion config**

Docs: [Playgrounds](https://launchdarkly.com/docs/home/agentcontrol/playground)

## What to test

Reuse the configs. Do not write a new briefing app.

| Source | What the playground compares |
|--------|------------------------------|
| [206-flags-vs-agent-management](../206-flags-vs-agent-management/) | Thoughtless Toby against Conservative Charlie, on the same headlines |
| [201-agent-completion-config](../201-agent-completion-config/) | One completion config. Change the model or the temperature and run again |

The criterion is the one 206 already cares about at runtime: the draft stays
inside the headlines and does not invent numbers. The playground shows that
**before** a variation is promoted. A run records the output, token use,
latency, and the score. It does not change the live config.

A later step, not this stub, is a dataset of several headline sets. That is
[705-offline-evaluations](../../70-model-demos/705-offline-evaluations/), on a
different product so it does not repeat this briefing.

## Do not

- Build another Generate screen. 201–206 already have one.
- Promote a variation as part of the first demo. The point is the sandbox.
- Treat this as online judges. Those are [204-agent-judges](../204-agent-judges/).

## When implementing

1. Pick 206's two variations as the columns. Fall back to 201 if 206's config
   is unavailable.
2. One fixed headline set, pasted in as variables.
3. One rubric: grounded in the headlines, no invented figures.
4. Write down the clicks. This example may never grow a language folder.
