# 15-prerequisite-flags

LaunchDarkly **flag prerequisites** for the lunch-marcoly grid navigator.

The dependent `show-navigation-move-count-prereq` flag evaluates normally only
when its parent `enable-grid-selection-highlight-prereq` flag is **on** and
serving **`green`**. Otherwise, the child serves its off variation and reports
`PREREQUISITE_FAILED`.

These keys cite [11-flag-enablement](../11-flag-enablement/) but are **not**
11's flags, so 11's independent count toggle is unchanged.

See [application.md](application.md) for the full specification.

Keywords: **prerequisites** · **dependent flag** · **off variation** ·
**evaluation reasons**

Docs: [Flag prerequisites](https://launchdarkly.com/docs/home/flags/prereqs)

## The dependency

```text
enable-grid-selection-highlight-prereq = green
                    │
                    ▼ prerequisite met
       show-navigation-move-count-prereq = true
```

| Parent | Child | Result |
|--------|-------|--------|
| On → `green` | On → `true` | Green highlight + Count |
| Off → `none` | On → `true` | No highlight; no Count |
| On → `yellow` | On → `true` | Yellow highlight; no Count |
| On → `green` | Off → `false` | Green highlight; no Count |

The application always asks the SDK for both variations. It does not implement
the dependency with application branching.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| Python web | [python/](python/) | Done |

## Environment

```bash
export LD_SDK_KEY="sdk-..."

# Optional in-app REST controls
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
```

```bash
(cd rest && chmod +x *.sh && ./create-flags.sh)
cd python && python 15-prerequisite-flags.py
```

Provisioning: [REST](rest/) creates the two `-prereq` flags and attaches
the child prerequisite. In-app Controls still cannot edit that relationship.

## Run

```bash
cd python
python 15-prerequisite-flags.py
```

Open http://127.0.0.1:8080/. Set `PORT` to override.

## Dedicated keys

| Role | 15 key | Cites 11 key |
|------|--------|----------------|
| Parent | `enable-grid-selection-highlight-prereq` | `enable-grid-selection-highlight` |
| Child | `show-navigation-move-count-prereq` | `show-navigation-move-count` |
