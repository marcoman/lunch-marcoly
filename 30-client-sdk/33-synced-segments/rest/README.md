# REST API provisioning

Create **`marcoly-inner-circle`** and **`show-inner-circle-badge`**, then add/remove
test members.

Keywords: **synced segments** · **unbounded** · **segmentMatch** · **big segment targets**

- [Post segment](https://launchdarkly.com/docs/api/segments/post-segment)
- [Update big segment targets](https://launchdarkly.com/docs/api/segments/update-big-segment-targets)

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
chmod +x *.sh
./create-flags.sh
./get-flag-status.sh
./add-member.sh alice
./remove-member.sh alice
```

| Script | Purpose |
|--------|---------|
| `create-flags.sh` | Segment (unbounded if allowed) + flag + segmentMatch rule |
| `get-flag-status.sh` | Demo snapshot (`--json` / `--verbose`) |
| `add-member.sh <key>` | Include a user context key |
| `remove-member.sh <key>` | Remove that key |
| `get-flag.sh <key>` | Compact flag JSON |
| `update-flag.sh` / `delete-flag.sh` | Same pattern as 31/32 |

`get-flag.sh` still takes a flag key (example: `show-inner-circle-badge`).
