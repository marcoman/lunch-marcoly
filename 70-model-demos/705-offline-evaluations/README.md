# 705-offline-evaluations

**Status: stub — not implemented yet.**

**Offline evaluations** for Agent Management, on a product that is not the
equity briefing. A small dataset of Terraform briefs runs through two model
variations. Each row comes back pass or fail. The screen is that table.

This lands in [70-model-demos](../README.md), not in
[20-agent-management](../../20-agent-management/). Online judges on the stock
picker already live in
[204-agent-judges](../../20-agent-management/204-agent-judges/). A playground
that compares Toby and Charlie before promotion is the unnumbered
[playgrounds](../../20-agent-management/playgrounds/) folder. This example is
the dataset run: same inputs, same rubric, every row scored, on
[704-terraform-codegen](../704-terraform-codegen/)'s job.

Keywords: **offline evaluations** · **datasets** · **Agent Management** ·
**acceptance criteria**

Docs: [Offline evaluations](https://launchdarkly.com/docs/home/agentcontrol/offline-evaluations)

## Suggested use case

About ten briefs. Each row names a flag key and a variation type. Two
variations generate `main.tf`:

| Variation | Role |
|-----------|------|
| Small local model | The one that usually misses the brief |
| Stronger hosted model | The one that usually keeps the flag key |

The rubric is narrow: the file mentions the requested flag key, and it is
Terraform rather than prose. No `terraform apply`. Acceptance criteria mark
the row pass or fail, with a one-line reason. Token use can sit beside the
score so a cheaper model that fails is still visible.

That is the difference from 704, which generates once and judges that file,
and from 204, which scores a live briefing.

Intended port **:8750** when a page is built. The first version can be the
evaluation run in LaunchDarkly, with the dataset checked in beside this
README. A local page is only worth it if the results table needs to sit next
to the briefs.

## Do not

- Reuse the equity-briefing prompts. That comparison is the playground stub.
- Attach the judge to live traffic. That is an online evaluation, already
  taught by 204.
- Score on taste. The row is pass or fail on the flag key and the file shape.

## When implementing

1. Write `application.md`: dataset columns, the two variations, and the
   rubric.
2. Keep the dataset small enough to read on one screen.
3. Record where the run lives (playground dataset versus SDK-from-code)
   after checking the current offline-evaluation docs.
