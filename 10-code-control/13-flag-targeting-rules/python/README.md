# Python (web)

Python web implementation of [13-flag-targeting-rules](../application.md), with the example 12 LaunchDarkly lab shell (Controls / Context / About) and Trace dock.

## Prerequisites

- Python 3.12+ and `launchdarkly-server-sdk`
- Provisioned `configure-team-label-style`
- `LD_SDK_KEY`
- For Controls: `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, `LD_ENVIRONMENT_KEY`

## Run

```bash
python 13-flag-targeting-rules.py
```

Open http://127.0.0.1:8080/. Set `PORT` to override the port.

The server uses `Config(sdk_key)` without private attributes. Selected teams are public `team` context attributes; No team omits the attribute.

## APIs

- `GET /api/flags?username=alice&team=red`
- `GET /api/bootstrap`
- `GET /api/flag-controls`
- `POST /api/flag-controls`

Controls change only flag on/off and fallthrough. Targeting rules remain provisioned through Terraform or REST.
