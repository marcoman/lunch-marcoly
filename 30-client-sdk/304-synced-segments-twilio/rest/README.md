# REST API provisioning

Creates **`show-twilio-inner-circle-badge`** with a `segmentMatch` rule.
Does **not** create the segment — Twilio Segment Audiences does, on first
LaunchDarkly Audiences sync.

Keywords: **Twilio Segment Audiences** · **synced segments** · **segmentMatch**

- [Syncing segments with Twilio Segment Audiences](https://launchdarkly.com/docs/home/flags/twilio)
- [Post feature flag](https://launchdarkly.com/docs/api/feature-flags/post-feature-flag)

Membership is **not** a REST call in this example. Join/leave is
`@segment/analytics-next` in the page. See
[parent README](../README.md#how-inner-circle-membership-works-twilio).

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
# After Twilio creates the segment, if the key is not the default:
# export LD_TWILIO_SEGMENT_KEY="the-key-from-the-ld-segments-page"
chmod +x *.sh
./create-flags.sh
./get-flag-status.sh
```

| Script | Purpose |
|--------|---------|
| `create-flags.sh` | Flag + segmentMatch (warns if the synced segment is missing) |
| `get-flag-status.sh` | Demo snapshot (`--json` / `--verbose`) |
| `get-flag.sh <key>` | Compact flag JSON |
| `update-flag.sh` / `delete-flag.sh` | Same pattern as 31–33 |

There is no `add-member.sh`. That was 33’s LaunchDarkly REST stand-in.
