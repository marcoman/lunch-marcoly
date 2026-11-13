# REST API provisioning

Create dedicated **105** flags and attach a [flag prerequisite](https://launchdarkly.com/docs/home/flags/prereqs):
both children require parent `enable-grid-selection-highlight-prereq` **on** and
serving **`green`**. The children are `show-navigation-move-count-prereq` and
`show-anonymous-host-os-emoji-prereq`.

These keys **cite** [101-flag-enablement](../../101-flag-enablement/) and do **not**
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
2. Creates both child boolean flags if missing (`true` / `false`)
3. `turnFlagOn` parent; off → `none`; fallthrough → `green`
4. `turnFlagOn` each child; off → `false`; fallthrough → `true`
5. `addPrerequisite` (or `updatePrerequisite` if already present) on each child:
   parent key, variation **green**

## Other examples

```bash
./get-flag.sh
./get-flag.sh enable-grid-selection-highlight-prereq
./update-flag.sh off parent    # aha: both children still on, Count and emoji hidden
./update-flag.sh on parent
./update-flag.sh off child
./update-flag.sh off emoji
./delete-flag.sh               # both children first, then parent
```

Do **not** use these scripts against 11's keys
(`enable-grid-selection-highlight`, `show-navigation-move-count`).
