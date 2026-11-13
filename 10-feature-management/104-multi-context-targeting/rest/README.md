# REST API provisioning

Create `show-partner-org-badge` and two **AND** [targeting rules](https://launchdarkly.com/docs/home/flags/target-rules)
on a [multi-context](https://launchdarkly.com/docs/home/flags/multi-contexts)
(`user` key + `organization` key).

Keywords: **multi-context** · **targeting rules** · **context kinds**

## Prerequisites

- `curl` and `jq`
- `LD_API_ACCESS_TOKEN`
- `LD_PROJECT_KEY`
- `LD_ENVIRONMENT_KEY` to apply on/off, fallthrough, and rules

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
chmod +x *.sh
./create-flags.sh
```

The create script:

1. Creates the boolean flag if missing (`true` / `false`)
2. `turnFlagOn`
3. Off variation and fallthrough → `false`
4. `addRule`: user `alice` **and** organization `acme` → `true`
5. `addRule`: user `bob` **and** organization `globex` → `true`

Other examples:

```bash
./get-flag.sh
./update-flag.sh off
./update-flag.sh on
./delete-flag.sh
```

Walk the 2×2 after the Python lab is up:

```bash
(cd .. && python collect-results.py --url http://127.0.0.1:8080)
```
