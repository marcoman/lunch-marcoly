# 21-tenant-datacenters

Five datacenters, 52 generated tenants. Each presence is one evaluation.
Two flags style the whole floor: a border palette, and a fill of that hue.
Version starts at 0, drawn as `7.0`.

The official shape is thousands of tenants across more than a dozen
datacenters. This lab keeps the same idea and shrinks the numbers.

Keywords: **feature flags** · **multivariate variations** · **boolean variations** · **segments** · **contexts**

Docs: [Variations](https://launchdarkly.com/docs/home/flags/variations) ·
[Boolean variations](https://launchdarkly.com/docs/home/flags/boolean) ·
[Segments](https://launchdarkly.com/docs/home/flags/segments) ·
[Contexts](https://launchdarkly.com/docs/home/flags/contexts)

## The floor

52 names, 106 boxes. A name that spans datacenters is drawn once in each.

| Datacenter | Boxes |
|------------|------:|
| DC01 | 22 |
| DC02 | 21 |
| DC03 | 21 |
| DC04 | 21 |
| DC05 | 21 |

Names come from two passes of A–Z. Vowels are Large. Q and Z are unknown.
Otherwise `(letter number − 1) % 3` picks Medium (2) or Small (0 or 1). Each
size has its own counter, and odd or even is that number.

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
customer starts where that Large started.

A is `L01`, size 7 version 0, drawn as `7.0`, in DC01, DC02, and DC03. B is
`S01`, size 1, in DC04.

## Flags

| Flag | Variations | Off serves |
|------|------------|------------|
| `tenant-border-palette` | `none`, `roygbiv`, `grays`, `earth`, `ocean` | `none` |
| `tenant-box-fill` | true, false | false |

One variation for every tenant. Size class picks the hue inside the palette,
so every Small is the same color in every datacenter. Yellow and orange stay
out of ROYGBIV so the light name still reads on a tinted fill. Fill with no
palette paints nothing.

Turning the border flag on, with no other rule, serves `roygbiv`. The Flags
tab does that with the same on/off and fallthrough control as the 10-series.
It needs `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY`
on the server. The palette applies to every box.

| Palette | Small | Medium | Large | Unknown |
|---------|-------|--------|-------|---------|
| roygbiv | blue | green | red | violet |
| grays | light | mid | white | dim |
| earth | moss | ochre | clay | stone |
| ocean | cyan | teal | sky | foam |

## Segments

Rules on the `tenant` context. Not used by the two color flags yet. A tenant
in all five datacenters also matches multi-site.

| Segment | Attribute |
|---------|-----------|
| `tenant-size-small` `tenant-size-medium` `tenant-size-large` `tenant-size-unknown` | `sizeClass` |
| `tenant-dc-01` … `tenant-dc-05` | `datacenter` |
| `tenant-footprint-single` | `span` is 1 |
| `tenant-footprint-multi` | `span` is 2, 3, or 5 |
| `tenant-footprint-all-five` | `span` is 5 |

Create them with [rest/create-all.sh](rest/create-all.sh).

## Customization

Copy [customizations.json.example](customizations.json.example) to
`customizations.json` in this directory. Set `companyName` and `logo`. The
logo is a file name in this directory, next to the example SVG. The local
copy is gitignored. If it is missing, the page uses the example values.

## Run

```bash
cd python
pip install -r requirements.txt
python 21-tenant-datacenters.py
```

Open http://127.0.0.1:8080/. `PORT` overrides the port. `LD_SDK_KEY` is the
server SDK key for the environment where the flags and segments live. Without
it, the border stays the hairline and the boxes stay empty.

## Later

Version releases still to wire: percentage rollout, progressive rollout, and
guarded rollout, moving instances from 0 through 9. Also bold, italic, and
icons in the open middle: database, firewall, robot, lock, then a failure
icon and an over-utilized icon.
