# 29-team-rollout

**Status: stub — not implemented yet.**

A **percentage rollout** on one AgentControl config. The rollout buckets by
the public **`team`** attribute, the same attribute
[13-flag-targeting-rules](../../10-code-control/13-flag-targeting-rules/) uses
(`red`, `blue`, `yellow`). Everyone on one team shares one assignment.

Switching the person does not change the variation. Switching the team does.

This is the agent-config version of the sticky split in
[16-percentage-rollout](../../10-code-control/16-percentage-rollout/), which
buckets by username. It is not
[14-progressive-rollout](../../99-use-cases/14-progressive-rollout/), which
moves 10% to 100% on a schedule.

Keywords: **percentage rollout** · **sticky bucketing** · **team** ·
**context attributes** · **AgentControl**

Docs: [Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts) ·
[Target an AgentControl config](https://launchdarkly.com/docs/home/agentcontrol/target)

## Intended aha

A fixed split across a few team names looks lumpy, and that is the demo. Some
teams get one prompt, the rest get the other. A new person who joins `red`
sticks with `red`. The screen shows the built context, the variation, and why
(the rollout bucket), so two people on the same team are obviously sharing
one assignment.

## Direction

- Bucket by `team`, not by the persona key.
- Toby, Betty, and the other briefing people are the users. The team control
  is separate from the person.
- Fixed percentage. Do not add rollout stages or a clock.
- Does not roll into [20-capstone](../20-capstone/).
- **Do not use ports :8290–:8293.** Those belong to the capstone. Pick ports
  when this lesson is built. Not in the series portal until then.

## When implementing

1. `application.md` with a new config key and two variations.
2. Python web first. The rail shows person, team, variation, and reason.
3. Log in as two people on `red` and one on `blue` to prove the bucket.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
