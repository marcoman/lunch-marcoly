# Python (web)

Python web implementation of [14-multi-context-targeting](../application.md).
Login and the lab rail use Alice/Bob and Acme/Globex radio cards. The rail keeps
the live multi-context JSON, current result, and event history visible while you
walk the 2×2. Tabs are Controls and About.

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
