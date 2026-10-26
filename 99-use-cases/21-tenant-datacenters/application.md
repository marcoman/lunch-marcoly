# 21-tenant-datacenters

A display of many single tenants across a few datacenters. The full reference
is thousands of tenants in more than a dozen datacenters. This example uses
five datacenters and 52 customers so the placement rule stays visible.

No flag is evaluated until `LD_SDK_KEY` is set. The drawer shows the controls,
a trace of flag and rollout changes, the segments, and the tenant context
that was sent.

## Placement

Two passes of A–Z. Letter number is A=1. Vowels are Large. Q and Z are unknown.
`(number − 1) % 3 == 2` is Medium. The other remainders are Small. `Y` is not
a vowel. Each size has its own counter, and that counter continues on the
second pass. Odd and even are the instance number.

| Instance | Datacenters | Size in each |
|----------|-------------|--------------|
| Odd Small | 1 | 1 |
| Even Small | 2 | 2 |
| Odd Medium | 1 | 5 |
| Even Medium | 3 | 5 |
| Odd Large | 3 | 7 |
| Even Large | 5 | 7 |
| Unknown | 1 | 3 |

One cursor walks DC01–DC05 and wraps. A customer takes the next N datacenters.
The same name is drawn in each. An even Large takes all five, so the next
customer starts on the datacenter where that Large started.

A is `L01`, size 7 version 0, in DC01, DC02, and DC03. B is `S01`, size 1, in DC04.
The subscript on each box is size.version, so a large reads `7.0`.
The floor has 52 names and 106 boxes. DC01 holds 22. The other four hold 21.
Each box spans the width of its datacenter. The open middle is for later icons.

## Screen

The upper left shows `companyName` and `logo` from `customizations.json`, or
from `customizations.json.example` when the local file is absent. Each
datacenter is a card. Each customer is a full-width monospace row, with
`size.version` as a subscript. The open middle is for later icons.

## Context

One context per presence. A tenant in three datacenters has three rows, with
the same key and a different datacenter. `version` is 0. `span` is how many
datacenters that customer occupies.

```json
{
  "kind": "tenant",
  "key": "L01",
  "size": 7,
  "sizeClass": "large",
  "version": 0,
  "span": 3,
  "datacenter": "DC01"
}
```

Contexts — https://launchdarkly.com/docs/home/flags/contexts

## Flags

The Toggles tab turns each flag on or off. On serves the true variation, unless
a rollout is already the default rule. Off only turns the flag off. Enable for
everybody serves the true variation from the default rule. The border palette
keeps its fallthrough picker. `tenant-border-palette` is one string for the whole floor: `none`, `roygbiv`,
`contrast`, `earth`, `ocean`, or `color-vision-aware`. Off serves `none`. Size class picks the hue, so
every Small matches. `tenant-box-fill` is a progressive rollout. Five one-minute steps serve
Fill to 5%, 10%, 25%, 50%, and 75% of tenant keys. After five minutes the
rollout finishes at 100%. Start it in LaunchDarkly on the default rule, with
context kind `tenant`, from Empty to Fill. Reset on the Manual tab turns the
flag off and serves Empty. `tenant-security` is a boolean lock. By name,
the lab targets `S01`, then the next name, 10 seconds apart, through Small,
Medium, and Large. By datacenter, it targets Large in `DC01`, then the next
datacenter, 10 seconds apart. Full deployment targets Small size 1, then
size 2, then Medium from `DC01` through `DC05`, then `L01`, 10 seconds
apart. Unknown stays off. Click the page once. Fill plays a tone at
the start, at each later percentage, and at the finish. Security plays at
the start, when the size or datacenter changes, and at the end.
`tenant-firewall` is a boolean icon on the Manual tab. True draws it. Off
draws nothing. The release phases are in the example README.

Variations — https://launchdarkly.com/docs/home/flags/variations
Individual targets — https://launchdarkly.com/docs/home/flags/individual-targeting
Targeting rules — https://launchdarkly.com/docs/home/flags/targeting-rules

## Segments

Size class, datacenter, and footprint (`span` 1, `span` 2/3/5, and `span` 5).
The datacenter wave on `tenant-security` matches large and one datacenter.
Full deployment matches Small on the size attribute, and Medium with the
medium segment plus one datacenter. The name wave, and Large in a full
deployment, use individual targets. A tenant in all five also matches
multi-site. The color flags do not target these segments.

Segments — https://launchdarkly.com/docs/home/flags/segments

## Not in this phase

Filled backgrounds beyond the palette tint, bold, italic, and the icons
(database, robot, failure, over-utilized) wait for a later
flag. The lock is `tenant-security`. The firewall is `tenant-firewall`.
So do the version releases: percentage, progressive, and guarded rollouts.
