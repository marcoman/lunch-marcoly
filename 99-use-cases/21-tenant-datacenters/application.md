# 21-tenant-datacenters

A display of many single tenants across a few datacenters. The full reference
is thousands of tenants in more than a dozen datacenters. This example uses
five datacenters and 52 customers so the placement rule stays visible.

No flag is evaluated until `LD_SDK_KEY` is set. The drawer shows the variation
that came back, the tenant context that was sent, and the segments.

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

`tenant-border-palette` is one string for the whole floor: `none`, `roygbiv`,
`grays`, `earth`, or `ocean`. Off serves `none`. Size class picks the hue, so
every Small matches. `tenant-box-fill` tints the box with that hue. A fill with no palette paints
nothing. The Flags tab turns the border flag on and sets its fallthrough.
That one variation is what every box evaluates.

Variations — https://launchdarkly.com/docs/home/flags/variations

## Segments

Size class, datacenter, and footprint (`span` 1, `span` 2/3/5, and `span` 5).
A tenant in all five also matches multi-site. The color flags do not target
these segments.

Segments — https://launchdarkly.com/docs/home/flags/segments

## Not in this phase

Filled backgrounds beyond the palette tint, bold, italic, and the icons
(database, firewall, robot, lock, failure, over-utilized) wait for a later
flag. So do the version releases: percentage, progressive, and guarded rollouts.
