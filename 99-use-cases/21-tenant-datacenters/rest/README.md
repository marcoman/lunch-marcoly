# REST setup

Creates `tenant-border-palette`, `tenant-box-fill`, and the size, datacenter,
and footprint segments. Segment keys match [flags.py](../flags.py).

The border flag is a string variation: `none`, `roygbiv`, `grays`, `earth`,
`ocean`. Off serves `none`. Turning it on, with no other rule, serves
`roygbiv`. The fill flag is a boolean. Off leaves the box empty.

Segments are rules on the `tenant` context. They are not targeting rules on
these two flags. A tenant in all five datacenters also matches multi-site.

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
./create-all.sh
```

[Feature flags — variations](https://launchdarkly.com/docs/home/flags/variations) ·
[Segments](https://launchdarkly.com/docs/home/flags/segments)
