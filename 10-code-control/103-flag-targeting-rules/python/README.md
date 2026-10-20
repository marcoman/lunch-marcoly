# Python (web)

Python web implementation of [103-flag-targeting-rules](../application.md), with the example 12 LaunchDarkly lab shell (Controls / Context / About) and Trace dock.

## Prerequisites

- Python 3.12+ and `launchdarkly-server-sdk`
- Provisioned `configure-team-label-style` and, for custom words, `configure-team-display-labels`
- `LD_SDK_KEY`
- For Controls: `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, `LD_ENVIRONMENT_KEY`

## Run

```bash
python 103-flag-targeting-rules.py
```

Open http://127.0.0.1:8080/. Set `PORT` to override the port.

The server uses `Config(sdk_key)` without private attributes. Selected teams are public `team` context attributes; No team omits the attribute. After login, the header switches among No team, Red, Blue, and Yellow without another login.

## Where to look

| What you see | Where it is |
|--------------|-------------|
| SDK client starts | `init_launchdarkly` |
| Browser poll that evaluates | `GET /api/flags` |
| Context, both evaluations, and the reason | `../team_style.py` `evaluate_team_style` |
| On/off and fallthrough only | `../ld_flag_controls.py` `apply_flag_control` |

Keywords: feature flags · targeting rules · context attributes · evaluation reasons · semantic patch

## APIs

- `GET /api/flags?username=alice&team=red`
- `GET /api/bootstrap`
- `GET /api/flag-controls`
- `POST /api/flag-controls`

Controls change only flag on/off and fallthrough. Targeting rules remain provisioned through Terraform or REST.
