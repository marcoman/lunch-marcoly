# Multitenant Datacenter

This document defines **24-multitenant-datacenter** under [99-use-cases](../README.md).

Status: the Python page on **:8788** evaluates the six flags and the Flags tab writes targeting. [rest/create-all.sh](rest/create-all.sh) creates those flags and segment `mtdc-gdpr-eu`. The other languages are not built yet.

## Goal

Show a floor of six datacenters, each modeled as a Kubernetes cluster. Every datacenter runs shared **multi-tenant** services. Some also run dedicated **single-tenant** services for named customers. The two EU datacenters are a separate **single-region** cohort for GDPR.

Flags light up three levels: the datacenter, the service, and the customer size inside a service. One evaluation reads all three through a **multi-context**.

[21-tenant-datacenters](../21-tenant-datacenters/) draws one box per tenant presence and uses a single `tenant` context. This example keeps its border palette, fill, lock, firewall, and version subscript, and moves them onto a hierarchy.

## Placement

### Datacenters

Six datacenters, named after AWS regions and drawn in three geography pairs.

| Geo | Datacenters | `gdpr` |
|-----|-------------|--------|
| `us` | `us-west-1`, `us-east-1` | false |
| `eu` | `eu-central-1`, `eu-west-1` | true |
| `ap` | `ap-southeast-1`, `ap-south-1` | false |

### Multi-tenant replicas

Every datacenter runs one shared multi-tenant service. The page names those replicas for the region: `usw1-1` and `usw1-2` in `us-west-1`, and the same pattern for `use1`, `euc1`, `euw1`, `apse1`, and `aps1`. `us-east-1` also shows `use1-3`. Later sizing can grow past that. A healthy cluster serves the same flag result on every replica that has the build. Flag rules do not target a replica number.

### Single-tenant replicas

A named customer gets its own replicas in a datacenter, named `ACME-1`, `ACME-2`, and so on. A large customer has one replica: `HUDSON-1` in `us-east-1`, `RHEIN-1` in `eu-central-1`, and `KOPI-1` in `ap-southeast-1`. ENZO in `us-west-1` is the exception and keeps two. ACME still matches `us-east-1` at three. BIGCO and DREX keep two.

A datacenter holds **0 to 2** named customers. Which customer goes in which datacenter is decided later. Until then the spec draws those places as empty slots.

### Customer sizes

Each replica box has three rows, one per customer size: **S**mall, **M**edium, and **L**arge. The row is where the customer-level features and the version are drawn. The customer panel, under the floor, is the view of what one named customer is served.

## Screen

The header reads **LaunchDarkly · lab**. Underline tabs sit directly under it. The floor stays visible while the tabs change. The tabs are **Rolling deployments** and **About**.

```text
┌ us-east-1 ───────────────────────────── border ┐
│ ┌ usw1-1 ─────────── fill ┐ ┌ usw1-2 ─── fill ┐ │
│ │ S  lock wall share horn S.2 │ │ S  ...       │ │
│ │ M  .    lock .     .   M.1 │ │ M  ...       │ │
│ │ L  .  .   .     .   L.0 │ │ L  ...          │ │
│ └─────────────────────────┘ └─────────────────┘ │
│ ┌ ACME-1 ─────────── fill ┐                     │
│ │ ...                     │                     │
└─────────────────────────────────────────────────┘
```

The lock is security. The brick wall is the firewall. Three linked nodes are data sharing. The horn is marketing. Every icon is always drawn. Faint means the replica does not have the build. Grey means the build is there and the flag is off. Color means the build is there and the flag is on. A change pulses that icon.

| State | When | How it looks |
|-------|------|----------------|
| Low-context | This replica does not have the build yet | Disabled |
| Muted | The replica has the build, and the flag is off for this row | Present, quiet |
| Ink | The replica has the build, and the flag is on for this row | Present, lit |

A dot in the sketch is muted or low-context. The version sits in a fixed column so it does not jump.

- **Datacenter card.** The region name and the border palette it is serving.
- **Replica box.** The replica name, and the fill it is serving. Multi-tenant boxes come first (`usw1-1`, `usw1-2`, and `use1-3` in `us-east-1`), then single-tenant boxes (`ACME-1`, …).
- **Size row.** Four icons: security, firewall, data sharing, marketing. Then the version. A legend in the header names them.
- **Customer panel.** A second view, under the floor. A few named customers, one Small, one Medium, and one Large, show what that customer is served. **The customer panel waits for both the roll and the flag.** An icon turns color there only when a rolled replica is serving that customer and the customer's context matches on name, size, and datacenter.
- **Now and Trace** work as in 21. Now shows the variation each flag is serving and how many rows changed on the latest update. Trace keeps one line per change.

## Two clocks

The floor runs two clocks. They do not share a schedule.

### Rolling deployment

A new capability arrives as a Kubernetes rolling deployment. This clock is independent of LaunchDarkly. One deployment exists for each capability that ships as a build: security, firewall, data sharing, and marketing. Each one walks on its own.

The walk is one datacenter at a time, in floor order: `us-west-1`, `us-east-1`, `eu-central-1`, `eu-west-1`, `ap-southeast-1`, `ap-south-1`. Inside a datacenter the shared replicas go first, `usw1-1` then `usw1-2`, and `use1-3` when that datacenter has it. Then each named customer, in name order, and that customer's replicas, `ACME-1` then `ACME-2`. A datacenter with no named customer skips that part. The next datacenter starts when the previous one finishes.

The delay between replicas is **1 second**. That includes the step from the last shared replica to the first customer replica, and the step into the next datacenter.

Until a replica is updated, its label for that capability stays low-context. After the update, the label is present. The flag then decides muted or ink.

The **Rolling deployments** tab lists the four deployments. Each has **Start**, **Stop**, and **Reset**.

| Button | What it does |
|--------|----------------|
| Start | Begins the walk, or resumes it, at the first replica still low-context for that capability |
| Stop | Pauses the walk. Replicas that already have the build keep it |
| Reset | Returns every replica to low-context for that capability. Flags stay as they are |

**All capabilities** walks the same replicas once per build: security, then firewall, then data sharing, then marketing. One build finishes before the next starts. The delay between replicas stays 1 second, including the step from the last replica of one build to the first replica of the next.

**Immediate deploy** sits once on the tab. It marks every capability rolled on every replica, with no delay. It is a fast-forward to the end of the software roll. It does not turn flags on. The customer panel still waits for the flag.

### Flag pass

Turning a flag on updates every replica that already has the build and matches the target, together. The target is a customer size (Small, Medium, or Large) or a datacenter. A replica still waiting on the roll stays low-context, even when the flag is on for its datacenter.

The customer panel is the place that combines the two. Cluster-on is not customer-on. The customer sees the label only after both clocks have reached them. An EU customer stays off for data sharing and marketing after both clocks finish.

### Version

The version is drawn like 21's `size.version` subscript, with the size letter: `S.0`, `M.0`, `L.0`.

| State | Version |
|-------|---------|
| Start | `0` |
| Security on | `1` |
| Security and firewall on | `2` |

Fill does not change the version. Data sharing and marketing do not change it either. Which version moves are a progressive rollout and which are a guarded rollout is decided later.

## Context

Each size row is one evaluation of a **multi-context** with three kinds. Each flag reads the kind that matches its level.

```json
{
  "kind": "multi",
  "datacenter": {
    "key": "eu-west-1",
    "geo": "eu",
    "gdpr": true
  },
  "service": {
    "key": "eu-west-1:S2",
    "name": "S2",
    "tenancy": "multi",
    "instances": 3
  },
  "customer": {
    "key": "eu-west-1:S2:M",
    "sizeClass": "medium",
    "tenancy": "multi"
  }
}
```

A single-tenant service sets `tenancy` to `single` and adds `"customer": "ACME"`. Its customer key is the customer name plus the size, for example `ACME:M`.

The service key and the customer key include the datacenter, so `euw1-2` and `use1-2` are different contexts. The replica name stays on the service context so the rolling deployment can walk `usw1-1`, then `usw1-2`. A flag rule targets `sizeClass` or the datacenter. It does not target the replica name. A named customer keeps one customer key wherever its replicas run.

Multi-contexts — https://launchdarkly.com/docs/home/flags/multi-contexts

## Flags

New keys, so the `tenant-*` flags in 21 stay independent.

| Flag | Type | Off serves | Context kind |
|------|------|------------|--------------|
| `mtdc-border-palette` | String: `none`, `roygbiv`, `contrast`, `earth`, `ocean`, `color-vision-aware` | `none` | `datacenter` |
| `mtdc-service-fill` | Boolean | false | `service` |
| `mtdc-security` | Boolean, lock icon | false | `customer` |
| `mtdc-firewall` | Boolean, firewall icon | false | `customer` |
| `mtdc-data-sharing` | Boolean, data sharing icon | false | `customer` |
| `mtdc-marketing` | Boolean, marketing icon | false | `customer` |

The palettes are the ones in 21.

Boolean variations — https://launchdarkly.com/docs/home/flags/boolean

Variations — https://launchdarkly.com/docs/home/flags/variations

## EU cohort

`eu-central-1` and `eu-west-1` are a single-region cohort. Nothing is shared with the other four datacenters.

- The `datacenter` context carries `gdpr: true` for those two.
- Segment `mtdc-gdpr-eu` matches kind `datacenter` where `gdpr` is true.
- The first targeting rule on `mtdc-data-sharing` and on `mtdc-marketing` serves `false` to `mtdc-gdpr-eu`. A later rollout on the default rule cannot turn those features on in the EU.

Other EU behavior is defined later. That includes keeping a single-tenant customer's services inside the EU when it is placed there.

## Segments

`mtdc-gdpr-eu` is created by [rest/create-all.sh](rest/create-all.sh). The size, tenancy, and geo segments are named here and are not created yet.

| Segment | Kind | Attribute |
|---------|------|-----------|
| `mtdc-size-small`, `mtdc-size-medium`, `mtdc-size-large` | `customer` | `sizeClass` |
| `mtdc-tenancy-multi`, `mtdc-tenancy-single` | `service` | `tenancy` |
| `mtdc-geo-us`, `mtdc-geo-eu`, `mtdc-geo-ap` | `datacenter` | `geo` |
| `mtdc-gdpr-eu` | `datacenter` | `gdpr` is true |

Segments — https://launchdarkly.com/docs/home/flags/segments

## Acceptance criteria

- [ ] Six datacenter cards, named after the AWS regions, in three geography pairs
- [ ] Region-coded shared replicas, two in each datacenter and three in `us-east-1`
- [ ] 0 to 2 named customers per datacenter, drawn as `C{n}-1` … `C{n}-3`
- [ ] Every replica box has S, M, and L rows
- [ ] Each row sends one multi-context with `datacenter`, `service`, and `customer` kinds, and the keys include the datacenter
- [ ] Border reads `datacenter`, fill reads `service`, the four row flags read `customer`
- [ ] A rolling deployment, independent of LaunchDarkly, walks one datacenter at a time: shared replicas, then each named customer's replicas, with 1 second between replicas
- [ ] The Rolling deployments tab has Start, Stop, and Reset for each capability, All capabilities walks one build at a time, and Immediate deploy finishes every roll with no delay and leaves the flags alone
- [ ] A flag targeted by size or datacenter lights every already-rolled replica that matches, together
- [ ] The customer panel waits for both the roll and the flag
- [ ] Each row shows firewall, security, data sharing, and marketing, then the version, in a fixed column
- [ ] The version is `0`, `1` with security, and `2` with security and firewall
- [ ] `mtdc-data-sharing` and `mtdc-marketing` serve `false` to `mtdc-gdpr-eu` before any other rule
- [ ] The page has a Rolling deployments tab and an About tab, and the floor stays visible while the tabs change

## Not in this phase

- Instance sizing beyond the defaults: 3 to 6 multi-tenant, 3 to 5 single-tenant
- Placing named customers in datacenters
- Which flags and version moves use a progressive rollout, and which use a guarded rollout
- Cascades or waves like 21
- Further EU behavior
- Size, tenancy, and geo segments, and Terraform provisioning
- Node, Java, and .NET pages

## Further reading

- [README.md](README.md)
- [21-tenant-datacenters](../21-tenant-datacenters/) — single tenant context, the palettes, the lock, the firewall
- [22-api-progressive-rollout](../22-api-progressive-rollout/) and [23-api-guarded-rollout](../23-api-guarded-rollout/) — the release APIs a later phase may use
