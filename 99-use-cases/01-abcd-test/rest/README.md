# REST API provisioning

Creates `configure-navigation-count-label` for the ABCD test. Flag defaults to **off** in `LD_ENVIRONMENT_KEY`.

## Environment variables

| Variable | Required |
|----------|----------|
| `LD_API_ACCESS_TOKEN` | Yes |
| `LD_PROJECT_KEY` | Yes |
| `LD_ENVIRONMENT_KEY` | Recommended |

## How to run

```bash
chmod +x *.sh
./create-flag.sh
./get-flag.sh configure-navigation-count-label
```

The experiment utility configures percentage rollout via the REST API when you run trials.
