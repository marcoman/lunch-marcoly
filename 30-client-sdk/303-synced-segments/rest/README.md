# REST API provisioning

Create **`marcoly-inner-circle`** and **`show-inner-circle-badge`**, then add/remove
test members. The membership scripts are the same LaunchDarkly calls the page
proxies as **Add to inner circle**.

Keywords: **synced segments** · **unbounded** · **segmentMatch** · **big segment
targets** · **included targets**

- [Synced segments](https://launchdarkly.com/docs/home/flags/synced-segments)
- [Post segment](https://launchdarkly.com/docs/api/segments/post-segment)
- [Update big segment targets](https://launchdarkly.com/docs/api/segments/update-big-segment-targets)
- [Patch segment](https://launchdarkly.com/docs/api/segments/patch-segment) (`addIncludedTargets` fallback)

Full causal chain (flag rule → REST → stream → badge):
[33 README — How inner-circle membership works](../README.md#how-inner-circle-membership-works).

## Add someone to the inner circle

`add-member.sh` tells LaunchDarkly to **include a user context key** on
`marcoly-inner-circle`. It does not turn the flag on; the flag is already
targeted by that segment.

1. **POST** [`/api/v2/segments/{project}/{env}/marcoly-inner-circle/users`](https://launchdarkly.com/docs/api/segments/update-big-segment-targets)
   with `{ "included": { "add": ["<key>"] } }`. LaunchDarkly stores `<key>` as an
   included target. Flags that `segmentMatch` this segment now evaluate `true`
   for that user.
2. If that endpoint rejects the segment (list-based fallback), **PATCH** the
   segment with semantic instruction `addIncludedTargets` for context kind
   `user`. Same membership result.

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
| `add-member.sh <key>` | Include a user context key (inner circle) |
| `remove-member.sh <key>` | Remove that key (`included.remove` / `removeIncludedTargets`) |
| `get-flag.sh <key>` | Compact flag JSON |
| `update-flag.sh` / `delete-flag.sh` | Same pattern as 31/32 |

`get-flag.sh` still takes a flag key (example: `show-inner-circle-badge`).
