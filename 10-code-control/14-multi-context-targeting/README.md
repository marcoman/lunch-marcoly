# 14-multi-context-targeting

LaunchDarkly **multi-context** targeting for the lunch-marcoly grid navigator.

The Python web lab evaluates `show-partner-org-badge` against a
[multi-context](https://launchdarkly.com/docs/home/flags/multi-contexts):
**user** + **organization**. Provisioned AND [targeting rules](https://launchdarkly.com/docs/home/flags/target-rules)
serve `true` only for two pairs.

See [application.md](application.md) for the full specification.

Keywords: **multi-context** · **context kinds** · **targeting rules** · **feature flags**

## The 2×2

| User | Org | Partner badge |
|------|-----|----------------|
| `alice` | `acme` | yes |
| `alice` | `globex` | no |
| `bob` | `acme` | no |
| `bob` | `globex` | yes |

Same person, other company → no. Same company, other person → no. Org is **not**
a `user` attribute (that was [13](../13-flag-targeting-rules/)).

The Python lab uses explicit **Alice / Bob** and **Acme / Globex** radio cards.
Its right rail keeps three things visible together as you walk the 2×2:

- the selected user and organization
- the exact JSON multi-context sent to LaunchDarkly
- current match status plus an event/evaluation history

## Provisioning

- [REST](rest/) creates the flag and the two AND rules.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| Python web | [python/](python/) | Done |

## Environment

```bash
export LD_SDK_KEY="sdk-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
export LD_API_ACCESS_TOKEN="api-..."
```

```bash
(cd rest && chmod +x *.sh && ./create-flags.sh)
cd python && python 14-multi-context-targeting.py
```

Open http://127.0.0.1:8080/. Set `PORT` to override.

## Collect results

Walks alice/bob × acme/globex (plus unmatched `carol`) and compares expected vs
SDK (or the running lab):

```bash
python collect-results.py
python collect-results.py --url http://127.0.0.1:8080
python collect-results.py --json
```
