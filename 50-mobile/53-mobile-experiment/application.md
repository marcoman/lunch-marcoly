# 53-mobile-experiment application specification

This example demonstrates one LaunchDarkly **Experimentation** test across the
native Android and iOS apps. It extends the 2×2 mobile navigator from
[51-reference](../51-reference/) and the mobile SDK setup from
[52-mobile-evaluation](../52-mobile-evaluation/).

Docs: [Designing experiments](https://launchdarkly.com/docs/guides/experimentation/designing-experiments) ·
[Mobile experimentation](https://launchdarkly.com/docs/sdk/features/experimentation) ·
[Experimentation events](https://launchdarkly.com/docs/home/experimentation/events)

Keywords: **Experimentation** · **mobile SDK** · **exposure** · **conversion** ·
**contexts** · **platform analysis**

## The teaching point

Android and iOS are **not** the treatments. The causal comparison is the
feature's control versus treatment:

| Variation | Experience |
|-----------|------------|
| `false` | Control: show the 2×2 grid immediately |
| `true` | Treatment: show a short **How to play** helper card, then the grid |

Both applications evaluate the same flag and track the same conversion. The
`platform` context attribute is an analysis dimension used to inspect treatment
effect separately for Android and iOS.

Do not claim that platform caused a result. Users are not randomly assigned to
an operating system.

## Hypothesis

If we show a short How to play card before the 2×2 grid, then more users will
complete their first successful orthogonal move than users who open the grid
immediately, because the card gives them greater confidence.

## Flag

| Attribute | Value |
|-----------|-------|
| Name | `Acme: mobile onboarding helper` |
| Key | `acme-mobile-onboarding-v2` |
| Type | boolean |
| Control | `false` |
| Treatment | `true` |
| SDK fallback / off variation | `false` |
| Mobile availability | `usingMobileKey: true` |

Do not create separate Android and iOS flags.

## Context

Use the same stable account key on either platform:

```text
{
  kind: "user",
  key: "<trimmed username>",
  platform: "android" | "ios",
  app-version: "1.0.0"
}
```

The context must be constructed before SDK initialization. The same context
identity is used for flag evaluation and event tracking. Do not use `platform`
to choose a variation in application code.

## Exposure and conversion

1. Initialize the mobile SDK with the stable context.
2. Evaluate `acme-mobile-onboarding-v2`. This evaluation establishes exposure.
3. Render control or treatment.
4. Track `mobile_onboarding_completed` once, after the user's first successful
   orthogonal grid move.
5. Never track completion for an invalid tap or more than once per login.

A conversion event without the preceding flag evaluation does not place a user
in the experiment.

## UI

The control opens on the normal 2×2 grid. The treatment first shows:

> **How to play**  
> Tap a square next to X. Your first successful move completes onboarding.

The treatment user taps **Continue** to reach the same grid. The grid displays
the served variation, platform, exposure state, and whether conversion has
been sent in its lab drawer.

## Experiment configuration

- Recommended experiment name: **First-run helper vs grid** (keep it distinct
  from flag display name **Acme: mobile onboarding helper**)
- Assignment: LaunchDarkly flag or config, default rule, randomize by `user`
- One experiment using `acme-mobile-onboarding-v2`
- Treatments: `false` control, `true` treatment
- Audience: 100% of `user` contexts, 50/50 split, reshuffling disabled
- Primary metric: custom event `mobile_onboarding_completed`
- Result attributes: `platform`, `app-version`
- Do not target treatment by platform
- Guardrails documented for the lesson: crash rate and onboarding latency

Start with an A/A validation if instrumentation confidence is low. Validate
both platforms have exposure and conversion events before interpreting lift.

## Classroom environment caveat

This repository defaults to project `lunch-marcoly`, but project selection is
always supplied through `LD_PROJECT_KEY`; it is not embedded in mobile code.
Concurrent classes sharing one environment also share flag targeting,
experiment allocation, and event results.

For isolation, each participant should use a distinct `LD_ENVIRONMENT_KEY` and
that environment's `LD_MOBILE_KEY`. This example documents those overrides but
does not create per-user environments or orchestrate multi-user isolation.

## Simulation

A host-side simulator may create stable synthetic users split between
`platform=android` and `platform=ios`, evaluate the same flag, and probabilistically
track the same conversion event. It must use an `LD_SDK_KEY` for the selected
environment and clearly label generated traffic as synthetic.

## Acceptance criteria

1. Android and iOS use the same flag and event keys.
2. Context contains stable user key, `platform`, and `app-version`.
3. Flag evaluation occurs before rendering either experience.
4. `false` opens the grid; `true` shows the helper then the same grid.
5. First valid move tracks one conversion; invalid/repeated moves do not.
6. Missing mobile key safely serves control and never exposes secrets.
7. The app shows platform as analysis metadata, never as assignment logic.
8. Provisioning targets the configured project/environment.
9. Documentation warns about shared classroom environments.
