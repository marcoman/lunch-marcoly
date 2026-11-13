# REST setup

Creates the six flags the page evaluates, plus segment `mtdc-gdpr-eu`.

| Flag | Type | Off serves |
|------|------|------------|
| `mtdc-border-palette` | `none`, `roygbiv`, `contrast`, `earth`, `ocean`, `color-vision-aware` | `none` |
| `mtdc-service-fill` | Boolean | false |
| `mtdc-security` | Boolean | false |
| `mtdc-firewall` | Boolean | false |
| `mtdc-data-sharing` | Boolean | false |
| `mtdc-marketing` | Boolean | false |

Boolean fallthrough is false, so turning a flag on does not serve true to everyone. The Flags tab adds the size-and-datacenter rule when you check both. `mtdc-data-sharing` and `mtdc-marketing` get a first rule that serves false to `mtdc-gdpr-eu`. A later rollout on the default rule leaves the EU off.

Running this again leaves an existing flag and an existing GDPR rule alone.

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="your-project"
export LD_ENVIRONMENT_KEY="your-environment"
./create-all.sh
```

The page reads `LD_SDK_KEY` to evaluate a clicked row, and the same three API variables to write targeting.

[Variations](https://launchdarkly.com/docs/home/flags/variations) ·
[Boolean variations](https://launchdarkly.com/docs/home/flags/boolean) ·
[Segments](https://launchdarkly.com/docs/home/flags/segments) ·
[Targeting rules](https://launchdarkly.com/docs/home/flags/targeting-rules)
