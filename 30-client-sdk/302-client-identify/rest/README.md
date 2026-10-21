# REST API provisioning

Create **32-client-identify** flags with **client-side availability** and
**key** targeting (`alice` / `bob`).

Keywords: **REST API** · **identify** · **addRule** · **clientSideAvailability**

- [Create a feature flag](https://launchdarkly.com/docs/api/feature-flags/post-feature-flag)
- [Target with rules](https://launchdarkly.com/docs/home/flags/target-rules)

## Environment variables

| Variable | Required |
|----------|----------|
| `LD_API_ACCESS_TOKEN` | Yes |
| `LD_PROJECT_KEY` | Yes |
| `LD_ENVIRONMENT_KEY` | For targeting rules |

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
chmod +x *.sh
./create-flags.sh
./get-flag-status.sh
```

| Script | Purpose |
|--------|---------|
| `create-flags.sh` | Flags + alice/bob rules, flags **on** |
| `get-flag-status.sh` | Demo snapshot (`--json` / `--verbose`) |
| `get-flag.sh <key>` | Compact JSON |
| `update-flag.sh <key>` | JSON Patch + turn on |
| `delete-flag.sh <key>` | Permanent delete |

Flag keys: `enable-identify-grid-highlight`, `show-identify-move-count`.
