# REST API provisioning

Creates `enable-grid-selection-highlight` as a **string** flag and helper scripts to toggle it.

## Environment variables

| Variable | Required |
|----------|----------|
| `LD_API_ACCESS_TOKEN` | Yes |
| `LD_PROJECT_KEY` | Yes |
| `LD_ENVIRONMENT_KEY` | Yes — environment **key** (e.g. `production`) |

## Scripts

| Script | Purpose |
|--------|---------|
| `./create-flag.sh` | Create flag (or replace non-string) and turn **off** |
| `./get-flag.sh` | Show on/off state and fallthrough color |
| `./turn-flag-on.sh [color]` | Turn **on**; default fallthrough `green` |
| `./turn-flag-off.sh` | Turn **off** (all users get `none`) |
| `./set-highlight-color.sh <color>` | Change fallthrough while flag is on |

```bash
chmod +x *.sh
./create-flag.sh
./turn-flag-on.sh green
./set-highlight-color.sh red
./get-flag.sh
./turn-flag-off.sh
```

Semantic patches use `variationId` as required by the LaunchDarkly REST API.

See [README.md](../README.md) for equivalent **curl** commands and UI steps.
