# Flags vs AgentControl — outline

**Status: Python app serves Original, Separate flags, and JSON flag.** Pass line is `0.65` (`JUDGE_PASS_THRESHOLD`). Message text lives in `rest/messages/`.

Human overview: [README.md](README.md).  
Series setup: [20-agent-config README](../README.md).  
Briefing shape: [21-agent-completion-config](../21-agent-completion-config/).  
Rewrite lesson, left alone: [24-agent-judges](../24-agent-judges/).

## Goal

One briefing screen. A source control picks where the model, the system prompt, the user prompt, and the judge switch come from.

| Source | Name in the UI | What LaunchDarkly serves |
|--------|----------------|--------------------------|
| Original | AgentControl | One **completion config** variation: model, system message, user message. Scoring uses a **judge config** |
| Separate flags | Separate flags | Four flags, evaluated on the same context |
| JSON flag | JSON flag | One JSON variation with `model`, `systemPrompt`, `userPrompt`, and `judge` |

The app substitutes headline text into the user prompt (`{{ stories }}`), calls the model, and streams the draft. When the judge is on, it scores that draft and decorates the output. It does not rewrite, regenerate, or edit the text.

Keywords: **feature flags** · **JSON variations** · **boolean variations** · **AgentControl** · **completion config** · **judges**

| Topic | Docs |
|-------|------|
| Flag types | [Flag types](https://launchdarkly.com/docs/sdk/features/flag-types) |
| AgentControl | [AgentControl](https://launchdarkly.com/docs/home/agentcontrol) |
| Completion config | [Quickstart for AgentControl](https://launchdarkly.com/docs/home/agentcontrol/quickstart) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| AI SDK | [AI SDKs](https://launchdarkly.com/docs/sdk/ai) |

## Personas

Two named personas. One targeting rule, one fallthrough. That is enough to show a completion config staying small while the flag sources multiply.

| Persona | Targeting | Voice | Model | Judge on the flag sources |
|---------|-----------|-------|-------|---------------------------|
| **Conservative Charlie** | Rule: user name is Charlie | Cautious | `llama3.2:3b` | On. Draft should **pass** |
| **Thoughtless Toby** | Fallthrough | Reckless | `llama3.2:1b` | On. Draft should **fail** |

No Amelia, no Nancy. A third persona would add another variation to every flag and would not teach a new idea.

On the Original source the judge config always scores. The pass/fail split still comes from the voice: Charlie’s variation is written to pass, Toby’s to fail.

## Sources

### Original

Dedicated completion config. Two variations, same targeting as the table above. Each variation holds the model, the system message, and the user message (`{{ stories }}`).

Scoring uses one dedicated judge config. The app calls it after the draft and shows the score. The judge is not a boolean inside the completion variation.

### Separate flags

| Flag | Kind | Charlie | Toby (fallthrough) |
|------|------|---------|---------------------|
| `configure-briefing-model` | string | `llama3.2:3b` | `llama3.2:1b` |
| `configure-briefing-system-prompt` | string | Cautious system text | Reckless system text |
| `configure-briefing-user-prompt` | string | Cautious user template with `{{ stories }}` | Reckless user template with `{{ stories }}` |
| `enable-briefing-judge` | boolean | `true` | `true` |

Each flag carries the same name rule. Four evaluations, four places to edit, four copies of the rule. The boolean is the conditional: `true` scores, `false` skips the judge and leaves the output plain.

Keys above are the proposed set. Confirm at build time. Do not reuse `equity-briefing-completion` or `equity-briefing-judged`.

### JSON flag

One flag, proposed key `configure-briefing-json`, kind JSON. Two variations, same name rule.

```json
{
  "model": "llama3.2:3b",
  "systemPrompt": "...",
  "userPrompt": "... {{ stories }}",
  "judge": true
}
```

Toby’s variation uses `llama3.2:1b`, the reckless prompt text, and `"judge": true`. One evaluation. The dashboard shows a blob.

## Screen

Same product shape as `21`: tickers, Get Stories, persona, Generate AI Report.

| Control | Effect |
|---------|--------|
| Source | AgentControl, Separate flags, or JSON flag. One Generate runs all three and leaves the drafts side by side |
| Persona | Charlie or Toby. Context name follows the persona |

After Generate, each column shows the model, whether the judge is on, the evaluation count, and the draft. Pass and fail color that column. **LD details** on a column opens that source. The drawer can switch to the other two without another Generate.

The screen shows Toby. When his draft fails the guardrail, AgentControl runs the Library tool `reduce-briefing-uncertainty` if `reckless-hype` has it attached. The handler softens certainty and appends a hedge. Separate flags and the JSON flag have no tool attachment, so those columns keep the failed draft.

When the guardrail is on, the draft panel takes a pass or fail treatment: the word Guardrail, a color, and an icon. The score is visible. When the guardrail is off, the panel stays plain. No second draft.

## Scope

- Web twins: Python **:8260**, Node **:8261**, Java **:8262**, .NET **:8263**.
- Python first.
- One judge, score only. Threshold number is chosen at build time and printed next to the score.
- `21` and `24` keep their keys, prompts, and rewrite behavior.

## Leave in place

- [21-agent-completion-config](../21-agent-completion-config/) — completion-config lesson.
- [24-agent-judges](../24-agent-judges/) — score, then rewrite once.
- [20-capstone](../20-capstone/) — composed graph. This example is the flag comparison.
- Series portal stays on `21`–`25` until this app exists.

## When implementing

1. Write the Charlie and Toby message text into this file, and pick the pass threshold.
2. REST provisioning for the completion config, the judge config, the four flags, and the JSON flag.
3. Python web, then the other web twins.
4. A Generate that hides the source, the evaluation count, or the pass/fail treatment fails the lesson.
