# Python (web)

Python web implementation of [14-multi-context-targeting](../application.md),
with the example 12 LaunchDarkly lab shell (Controls / Context / About) and Trace
dock.

## Prerequisites

- Python 3.12+ and `launchdarkly-server-sdk`
- Provisioned `show-partner-org-badge`
- `LD_SDK_KEY`
- For Controls: `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, `LD_ENVIRONMENT_KEY`

## Run

```bash
python 14-multi-context-targeting.py
```

Open http://127.0.0.1:8080/. Set `PORT` to override the port.

The server builds a **multi-context** (`user` + `organization`) and calls
`variation_detail`. Application code does not hard-code the alice/bob matrix.

## APIs

- `GET /api/flags?username=alice&org=acme`
- `GET /api/bootstrap`
- `GET /api/flag-controls`
- `POST /api/flag-controls`

Controls change only flag on/off and fallthrough. Targeting rules remain
provisioned through REST.

Walk the 2×2 from the lab rail, or:

```bash
python ../collect-results.py --url http://127.0.0.1:8080
```
