# Flag Targeting Rules Application Specification

This document defines the flag and desired effects for **13-flag-targeting-rules**.

Baseline login, grid navigation, header positions, and session controls come from [00-reference-code/application.md](../../00-reference-code/application.md). This example adds a team picker and one LaunchDarkly string flag.

## Overview

This lab teaches **targeting rules** on a public **context attribute**. It contrasts with [11-flag-enablement](../11-flag-enablement/), where application code parses a username into a cohort. Here the application supplies `team`; LaunchDarkly rules decide which style to serve.

- [Targeting rules](https://launchdarkly.com/docs/home/flags/target-rules)
- [Context attributes](https://launchdarkly.com/docs/home/flags/context-attributes)

Python, Node.js, and Java are also available as console applications. They keep the login, team targeting, live flag refresh, and grid navigation behavior, but intentionally omit the web lab and REST Controls.

## Flag

| Attribute | Value |
|-----------|-------|
| Name | `Configure: team label style` |
| Key | `configure-team-label-style` |
| Type | String, multivariate |
| Temporary | No |
| Off variation | `plain` |
| Fallthrough | `plain` |
| Environment default | On |

### Variations

| Value | Effect |
|-------|--------|
| `plain` | Team label uses inherited text color |
| `colored-red` | Team label uses red CSS color |
| `colored-blue` | Team label uses blue CSS color |
| `colored-yellow` | Team label uses yellow CSS color |

### Targeting rules

Rules are evaluated in this order:

| Context clause | Served variation |
|----------------|------------------|
| `team` is `red` | `colored-red` |
| `team` is `blue` | `colored-blue` |
| `team` is `yellow` | `colored-yellow` |
| No rule matches | `plain` |
| Flag off | `plain` |

Rules are provisioned through [terraform/](terraform/) or [rest/create-flags.sh](rest/create-flags.sh). The in-app Controls tab does not edit them.

## Login and context

Login requires a username and offers:

- No team
- Team Red
- Team Blue
- Team Yellow

The evaluation context is kind `user` with `key=username`. For a selected team, the context includes public attribute `team` with value `red`, `blue`, or `yellow`. For **No team**, the application omits `team` entirely; all team rules skip and fallthrough serves `plain`.

The attribute is intentionally public. Do not configure it as private: analytics should receive it.

## Header behavior

The header always shows:

```text
Name: alice
Team: Team Red
Current position: m/m
Previous position: —
```

Only the team label text changes color. `plain` and flag-off behavior must not assign a label color.

## LaunchDarkly lab

The permanent shell matches example 12:

- **Controls** — on/off and fallthrough selector for the one flag
- **Context** — user key and public team, or `(omitted — No team)`
- **About** — targeting-rules explanation and provisioning note
- **Trace** — login with team, SDK served style/team/reason, and REST control actions

## API

`GET /api/flags?username=alice&team=red` accepts `team` as empty, `red`, `blue`, or `yellow`.

```json
{
  "team": "red",
  "teamLabel": "Team Red",
  "style": "colored-red",
  "colored": true,
  "cssColor": "red",
  "ldContext": {
    "kind": "user",
    "key": "alice",
    "attributes": {"team": "red"}
  },
  "variationIndex": 1,
  "reason": {"kind": "RULE_MATCH", "ruleIndex": 0}
}
```

`GET /api/bootstrap` returns the banner and control configuration. `GET` and `POST /api/flag-controls` expose status, on/off, and fallthrough changes following example 12.

## Acceptance criteria

1. Login offers the four locked team choices and the header always displays the team label.
2. The context key equals username.
3. Selected teams set public `team`; No team omits it entirely.
4. Red, blue, and yellow rules serve their matching colored styles.
5. No team, unmatched contexts, and flag-off evaluations serve `plain`.
6. Controls modify only on/off and fallthrough, never rules.
7. Trace logs login team, SDK evaluations, and REST actions.
8. REST and Terraform provisioning create the four variations and three rules.
