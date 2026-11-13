# 30-pii

**Status: stub — not implemented yet.**

A data-entry screen with three fields, and two flag evaluations. The
LaunchDarkly context page is the proof of what left the process.

The context is searchable. Its key is an opaque id the server generates.
The key is always sent, and it cannot be marked private, so it is never the
email and never the child's name.

| Field | On the context | What changes |
|-------|----------------|--------------|
| Region: `us-east-1`, `us-west-1`, `eu-central-1` | Public attribute `region` | String flag serves a different response for each region. The context page shows the region. |
| Email | Private attribute `email` | A second flag targets a known domain. The variation changes. The value is not on the context page. |
| Child's name | Never added | Nothing. Editing the name does not change either evaluation. |

`101` and `102` already mark `hostOs` private and use an anonymous context for
an emoji. This example is the customer question: which of these three values
arrives.

Keywords: **contexts** · **private attributes** · **PII**

Docs: [Private attributes](https://launchdarkly.com/docs/sdk/features/private-attributes) ·
[Using private context attributes](https://launchdarkly.com/docs/home/flags/private-context-attributes)

## Why the context is searchable

Anonymous keeps a context off the Contexts list. It does not remove attributes
from events. LaunchDarkly recommends private attributes when the goal is to
keep a value out.
[Anonymous contexts](https://launchdarkly.com/docs/home/flags/anonymous-contexts).

A searchable context makes the lesson visible. Open the context for the key
on the page. Region is there. Email is not. The child's name is not.

## Flags

Python server. Intended port **:8790**. The server SDK evaluates locally, and
it does not send a private attribute back to LaunchDarkly.

| Flag | Rule |
|------|------|
| Region response, string | One variation each for `us-east-1`, `us-west-1`, and `eu-central-1`. Fallthrough is a fourth, for an empty region. |
| Staff badge, boolean | `email` ends with `@example.com`. On when it matches. The attribute is private, so the match happens in the SDK and the address does not leave the process. |

The page shows both variations, the context key, and the context the SDK
built: `region` present, `email` marked private, child name absent. It tells
the runner to open that key under Contexts and compare.

Type a fictional name. The server discards it before building the context.
Do not log it, and do not put a real name in a fixture.

## Do not

- Mark the child's name private. That is the email case.
- Use the name or the email as the context key.
- Switch this context to anonymous to "hide the PII."
- Use a client SDK here. A client SDK sends a private attribute for
  evaluation and then does not store it. That is a different sentence.

## When implementing

1. `application.md` with both flag keys, the three region variations, and the
   `@example.com` rule.
2. One Python page. About tab under **LaunchDarkly · lab**: the three fields,
   the two evaluations, and the private-attributes docs link.
3. A control that regenerates the opaque key, so a second submit is a new
   context rather than an edit of the first.
