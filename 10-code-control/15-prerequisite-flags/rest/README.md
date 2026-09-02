# REST API provisioning

Create dedicated **15** flags and attach a [flag prerequisite](https://launchdarkly.com/docs/home/flags/prereqs):
child `show-navigation-move-count-prereq` requires parent
`enable-grid-selection-highlight-prereq` **on** and serving **`green`**.

These keys **cite** [11-flag-enablement](../../11-flag-enablement/) and do **not**
patch 11's inventory.

Keywords: **prerequisites** · **dependent flag** · **semantic patch** ·
**addPrerequisite**

## Prerequisites

- `curl` and `jq`
- `LD_API_ACCESS_TOKEN`
- `LD_PROJECT_KEY`
- `LD_ENVIRONMENT_KEY` to apply on/off, fallthrough, and the prerequisite

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
chmod +x *.sh
./create-flags.sh
```

The create script:

1. Creates the parent string flag if missing (`none` / colors)
2. Creates the child boolean flag if missing (`true` / `false`)
3. `turnFlagOn` parent; off → `none`; fallthrough → `green`
4. `turnFlagOn` child; off → `false`; fallthrough → `true`
5. `addPrerequisite` (or `updatePrerequisite` if already present): parent key,
   variation **green**

## Other examples

```bash
./get-flag.sh
./get-flag.sh enable-grid-selection-highlight-prereq
./update-flag.sh off parent    # aha: child still on, Count hidden
./update-flag.sh on parent
./update-flag.sh off child
./delete-flag.sh               # child first, then parent
```

Do **not** use these scripts against 11's keys
(`enable-grid-selection-highlight`, `show-navigation-move-count`).
