# Multi-context targeting application specification

This document defines **14-multi-context-targeting**.

Baseline login, grid navigation, header positions, session controls, and
`X`-only selection come from
[00-reference-code/application.md](../../00-reference-code/application.md).
This example adds an **organization** picker and one LaunchDarkly **boolean**
flag evaluated against a **multi-context**.

## Overview

This lab teaches **multi-contexts**: one evaluation sends more than one context
kind so targeting can require **user and organization together**.

It is **not** [13-flag-targeting-rules](../13-flag-targeting-rules/). **13**
puts `team` on a single `user` context. **14** uses `kind: "multi"` with
associated **user** and **organization** contexts. Application code must not
encode “alice-at-acme” as a username trick; LaunchDarkly rules decide the pair.

Keywords: **multi-context** · **context kinds** · **targeting rules** ·
**feature flags**

Docs: [Multi-contexts](https://launchdarkly.com/docs/home/flags/multi-contexts) ·
[Targeting rules](https://launchdarkly.com/docs/home/flags/target-rules) ·
[Contexts](https://launchdarkly.com/docs/home/flags/contexts)

Python, Node.js, Java, C++, Go, and Rust are also available as console
applications. They keep login, org choice, live flag refresh, and grid
navigation, but omit the web lab and REST Controls.

## The 2×2 (the whole lesson)

Login name is the **user** context key (normalized). Org picker is the
**organization** context key. Only two pairs are “in”:

| User key | Organization key | Flag (`show-partner-org-badge`) |
|----------|------------------|-----------------------------------|
| `alice` | `acme` | **true** — partner badge |
| `alice` | `globex` | **false** — no badge |
| `bob` | `acme` | **false** — no badge |
| `bob` | `globex` | **true** — partner badge |
| any other user, either org | | **false** |
| flag off | | **false** |

Alice is a partner at Acme only. Bob is a partner at Globex only. Same person,
other company → no result. Same company, other person → no result.

## Flag

| Attribute | Value |
|-----------|-------|
| **Kind** | Show (temporary) |
| **Name** | `Show: partner org badge` |
| **Key** | `show-partner-org-badge` |
| **Variation type** | boolean |
| **Temporary** | Yes |
| **Tags** | `grid-navigator`, `show`, `multi-context`, `targeting` |
| **Off variation** | `false` |
| **Fallthrough** | `false` |
| **Environment default** | On |
| **SDK default when offline** | `false` |

When `true`, the header shows a **partner** badge next to the username (same
idea as the 33 inner-circle chip: visible, not a second grid theme). When
`false`, no badge. Selected cell stays **`X` only** (matches 00 and 13).

### Targeting rules

Rules AND two clauses (each clause names a **context kind**). Order:

| Rule | Clauses | Serve |
|------|---------|-------|
| 1 | `user` key is `alice` **and** `organization` key is `acme` | `true` |
| 2 | `user` key is `bob` **and** `organization` key is `globex` | `true` |
| (none) | Fallthrough | `false` |
| Flag off | Off variation | `false` |

Do not implement this matrix in application `if` statements. Provision the
rules with [terraform/](terraform/) or [rest/](rest/). Lab Controls may change
**on/off** (and optionally fallthrough). They must **not** edit rules.

## Login and context

Login requires one of two explicit **user** choices and one **organization**
choice. Both use radio-card controls so the active pair is unambiguous:

| Label | User context key |
|-------|------------------|
| Alice | `alice` |
| Bob | `bob` |

| Label | Organization context key | Organization `name` (public) |
|-------|--------------------------|------------------------------|
| Acme | `acme` | `Acme` |
| Globex | `globex` | `Globex` |

Do not add org onto the user object.

Every evaluation uses a **multi-context**:

```json
{
  "kind": "multi",
  "user": {
    "key": "alice"
  },
  "organization": {
    "key": "acme",
    "name": "Acme"
  }
}
```

`name` on organization is public (analytics). Do not mark these attributes
private.

On the grid, persistent radio-card groups in the lab rail (or equivalent
console prompts) let the operator walk the 2×2 **without logout**:

- Set user to **Alice** / **Bob** (sets the user key; keeps current org)
- Set org to **Acme** / **Globex** (keeps current user key)

Each change builds a new multi-context and re-evaluates. Server-side SDKs send
the updated context on the next variation call; this example is not the
client-side `identify()` lesson ([32-client-identify](../../30-client-sdk/32-client-identify/)).

## Header behavior

Always show org. Badge only when the flag is `true`:

```text
Name: alice                    ← plus partner badge when true
Org: Acme
Current position: m/m
Previous position: —
```

Unmatched pairs still show **Org: Globex** (or Acme); they just omit the badge.

## LaunchDarkly lab

The permanent shell keeps the teaching evidence visible while the pair changes:

- **Controls** — on/off for `show-partner-org-badge` (leave **on** for the demo)
- **Context window (always visible)** — pretty-printed multi-context (user key
  + organization key/name)
- **Current result (always visible)** — match/no-match, badge state, and
  evaluation reason
- **Events / status rail (always visible)** — user/org changes, SDK variation
  result, reason, and REST control actions
- **About** — 2×2 table, multi-context keywords, docs links above

## API

`GET /api/flags?username=alice&org=acme` — `org` is `acme` or `globex`.
Username is lowercased for the user key.

```json
{
  "username": "alice",
  "org": "acme",
  "orgLabel": "Acme",
  "partner": true,
  "ldContext": {
    "kind": "multi",
    "user": { "key": "alice" },
    "organization": { "key": "acme", "name": "Acme" }
  },
  "reason": { "kind": "RULE_MATCH", "ruleIndex": 0 }
}
```

Unmatched example (`alice` + `globex`): `"partner": false`, reason fallthrough
(or `OFF` if the flag is off).

`GET /api/bootstrap` returns the banner and control configuration.
`GET` and `POST /api/flag-controls` expose status and on/off following example
12. Optional `POST` to switch user/org for the session if the web app keeps
context server-side; otherwise query params on `/api/flags` are enough.

## Acceptance criteria

1. Login requires Alice or Bob and Acme or Globex, using obvious radio-card
   groups (no free-form user, third org, or omitted org)
2. Evaluation context is `kind: "multi"` with `user` and `organization` only
3. User key is lowercased username; org key is `acme` or `globex`
4. `alice`+`acme` and `bob`+`globex` serve `true` (partner badge) when the flag is on
5. `alice`+`globex`, `bob`+`acme`, and any other user serve `false`
6. Flag off serves `false` even for a matching pair
7. Alice/Bob and Acme/Globex radio controls (or console equivalents) walk the
   2×2 without logout
8. Application code does not hard-code the pair matrix; the SDK variation is the source of truth
9. Controls modify only on/off (and optional fallthrough), never targeting rules
10. Live context, current result, and events/status remain visible together
    while selections change
11. REST and Terraform create the boolean flag, two AND rules, fallthrough
    `false`, flag on

## Further reading

- [13-flag-targeting-rules/application.md](../13-flag-targeting-rules/application.md)
- [00-reference-code/application.md](../../00-reference-code/application.md)
