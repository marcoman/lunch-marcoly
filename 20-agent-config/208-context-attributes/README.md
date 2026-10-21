# 28-context-attributes

**Status: stub — not implemented yet.**

Build a context from two choices, show that context, then serve the
AgentControl variation those attributes select.

- **Region:** North America or South America.
- **Audience:** a second attribute with two values.

This is **context-attribute targeting**. It is not prompt-variable
interpolation (`{{ audience }}` inside a message). Leave templates for another
lesson.

Keywords: **contexts** · **context attributes** · **targeting** ·
**AgentControl**

Docs: [Context attributes](https://launchdarkly.com/docs/home/flags/context-attributes) ·
[Target an AgentControl config](https://launchdarkly.com/docs/home/agentcontrol/target)

## Intended aha

The page shows the context it is about to send. North America and South
America select different variations. The audience choice does too. The reply
matches the variation those attributes selected, and the screen says which
variation came back.

## Direction

- Toggles build the context. A button generates.
- Show the context before the call, and the served variation after it.
- One idea: attributes select a variation. Do not also teach `{{ }}`
  substitution here.
- Not in the series portal until the app exists. Intended ports **:8280–:8283**.
- Does not roll into [20-capstone](../20-capstone/).

## When implementing

1. `application.md` with a new config key and the two attributes.
2. Python web first.
3. The rail prints the context JSON next to the variation key.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
