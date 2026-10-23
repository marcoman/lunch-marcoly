# REST setup

Creates `tenant-border-palette`, `tenant-box-fill`, `tenant-security`, `tenant-firewall`, and the size, datacenter,
and footprint segments. Segment keys match [flags.py](../flags.py).

The border flag is a string variation: `none`, `roygbiv`, `contrast`, `earth`,
`ocean`, `color-vision-aware`. Off serves `none`. Turning it on, with no other
rule, serves `roygbiv`. The fill flag is a boolean. Off leaves the box empty. Its
description includes a link to the flag in this project and environment.

Segments are rules on the `tenant` context. The datacenter wave on
`tenant-security` matches `tenant-size-large` and one `tenant-dc-0N`
segment. Full deployment matches Small on the size attribute, and Medium
with `tenant-size-medium` plus one datacenter segment. The name wave, and
Large in a full deployment, use individual targets. The color flags do not
use the segments. A tenant in all five datacenters also matches multi-site.

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
./create-all.sh
```

[Feature flags — variations](https://launchdarkly.com/docs/home/flags/variations) ·
[Segments](https://launchdarkly.com/docs/home/flags/segments)
