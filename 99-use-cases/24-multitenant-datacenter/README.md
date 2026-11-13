# 24-multitenant-datacenter

Status: Python presentation on **:8788**. The Flags tab writes targeting and a clicked row evaluates the six flags. [rest/create-all.sh](rest/create-all.sh) creates the flags and segment `mtdc-gdpr-eu`. Other languages come later.

```bash
cd python && python 24-multitenant-datacenter.py
```

Open http://127.0.0.1:8788/ . Shared replicas take the region code: `usw1-1`, `use1-1`, `euc1-1`, `euw1-1`, `apse1-1`, `aps1-1`. `us-east-1` has a third, `use1-3`. The named customers on the floor are a stand-in: ENZO in `us-west-1`, ACME and HUDSON in `us-east-1`, BIGCO and RHEIN in `eu-central-1`, and DREX and KOPI in `ap-southeast-1`. Each datacenter header shows a simulated share of 1,000 customers: US 50%, EU 30%, AP 20%, and `ap-south-1` is a quarter of AP. Within a region the split is 50% small, 30% medium, 15% large, and 5% named. The customer panel is a representative sample, five names in each size column.

Six datacenters, named after AWS regions. Each one is a Kubernetes cluster. Shared replicas are named for the region, `usw1-1` and `usw1-2`. `us-east-1` also runs `use1-3`. A large customer has one dedicated replica: `HUDSON-1`, `RHEIN-1`, and `KOPI-1`. ENZO in `us-west-1` is the exception and keeps two. ACME still has three in `us-east-1`. BIGCO and DREX keep two. Inside every replica are three rows for customer size: **S**, **M**, **L**.

Flags work at three levels. Border color belongs to the datacenter. Fill belongs to the service. Security, firewall, data sharing, and marketing belong to the customer size row, along with the version. One evaluation per row sends a **multi-context** that holds all three.

`eu-central-1` and `eu-west-1` are a single-region cohort for GDPR. Data sharing and marketing never turn on there.

Keywords: **feature flags** · **multi-contexts** · **boolean variations** · **multivariate variations** · **segments** · **targeting rules**

Docs: [Multi-contexts](https://launchdarkly.com/docs/home/flags/multi-contexts) ·
[Segments](https://launchdarkly.com/docs/home/flags/segments) ·
[Boolean variations](https://launchdarkly.com/docs/home/flags/boolean)

## The floor

| Geo | Datacenters | Multi-tenant | Named customers |
|-----|-------------|--------------|-----------------|
| US | `us-west-1`, `us-east-1` | `usw1-1`…, `use1-1`…`use1-3` | 0 to 2 per datacenter |
| EU (GDPR) | `eu-central-1`, `eu-west-1` | `euc1-1`…, `euw1-1`… | 0 to 2 per datacenter |
| AP | `ap-southeast-1`, `ap-south-1` | `apse1-1`…, `aps1-1`… | 0 to 2 per datacenter |

A large customer's dedicated set is one replica. ENZO in `us-west-1` keeps two.

## What each level shows

```text
Datacenter: us-east-1             border
  Service: usw1-1                 fill
    S   lock  wall  share  horn   S.0
    M   ...                                   M.0
    L   ...                                   L.0
  Service: ACME-1                 fill
    ...
```

The four icons are always on the row. The header legend names them: a lock, a brick wall, linked nodes, and a horn. Faint means this replica does not have the build yet. Grey means the build is there and the flag is off. Color means the build is there and the flag is on. Deploy, enable, and disable pulse the icon that changed.

The version starts at `0`. Security makes it `1`. Security and firewall make it `2`, the same rule as [21-tenant-datacenters](../21-tenant-datacenters/).

## Two clocks

A Kubernetes rolling deployment is independent of LaunchDarkly. One deployment exists for each build: security, firewall, data sharing, and marketing. The walk takes one datacenter at a time, in floor order. Inside a datacenter the shared replicas go first (`usw1-1`, then `usw1-2`), then each named customer's replicas. The delay is 1 second between replicas. An icon stays faint until that replica has the build.

The Rolling deployments tab gives each deployment **Start**, **Stop**, and **Reset**. Start begins or resumes the walk. Stop pauses it. Reset returns that capability to low-context on every replica and leaves the flags alone. **All capabilities** runs that walk once per build, security then firewall then data sharing then marketing, and starts the next build only after the previous one finishes. **Immediate deploy** finishes every roll immediately, with no delay, so the floor can jump to the end of the software roll. It does not turn flags on.

A flag targets a size or a datacenter. Every replica that already has the build and matches the target updates together. A replica still waiting on the roll stays low-context.

## Customer panel

Under the floor, a few named customers stand in for Small, Medium, and Large. This panel shows what that customer is served.

The customer panel waits for both the roll and the flag. A label lights for a customer only when a rolled replica is serving them and their context matches on name, size, and datacenter. Data sharing and marketing stay off for an EU customer after both clocks finish.

## Flags

| Flag | Level | Context kind |
|------|-------|--------------|
| `mtdc-border-palette` | Datacenter | `datacenter` |
| `mtdc-service-fill` | Service | `service` |
| `mtdc-security` | Customer size | `customer` |
| `mtdc-firewall` | Customer size | `customer` |
| `mtdc-data-sharing` | Customer size | `customer` |
| `mtdc-marketing` | Customer size | `customer` |

The first rule on `mtdc-data-sharing` and `mtdc-marketing` serves `false` to segment `mtdc-gdpr-eu`. A later rollout on the default rule leaves the EU off. Create the flags with [rest/create-all.sh](rest/create-all.sh).

## About

The idea is one evaluation that answers at three levels, after the build has landed. The datacenter context picks the border. The service context picks the fill. The customer context picks the row features. To try it:

1. On Rolling deployments, start one capability, or start All capabilities and watch one build finish before the next. Immediate deploy skips the wait.
2. Turn on a flag for one size, or one datacenter. Every replica that already has the build and matches the target lights together.
3. Read the customer panel. It waits for both the roll and the flag. An EU customer stays off for data sharing and marketing.

[Multi-contexts](https://launchdarkly.com/docs/home/flags/multi-contexts)

## Later

- Instance sizing beyond the defaults
- Placing named customers in datacenters
- Which changes use a progressive rollout and which use a guarded rollout
- Further EU behavior
- Port, language folders, and Terraform

See [application.md](application.md) for the full spec.
