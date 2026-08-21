# REST API provisioning

Create `configure-team-label-style` and its three [targeting rules](https://launchdarkly.com/docs/home/flags/target-rules) with the LaunchDarkly REST API.

## Prerequisites

- `curl` and `jq`
- `LD_API_ACCESS_TOKEN`
- `LD_PROJECT_KEY`
- `LD_ENVIRONMENT_KEY` to apply on/off, fallthrough, and rules

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="test"
chmod +x *.sh
./create-flags.sh
```

The create script reads variation IDs after flag creation, then sends semantic-patch instructions for:

1. `turnFlagOn`
2. off variation and fallthrough → `plain`
3. `addRule`: `team=red` → `colored-red`
4. `addRule`: `team=blue` → `colored-blue`
5. `addRule`: `team=yellow` → `colored-yellow`

Other examples:

```bash
./get-flag.sh
./update-flag.sh off
./update-flag.sh on
./delete-flag.sh
```
