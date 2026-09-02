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
| Node web | [node/](node/) | Done |
| Java web | [java/](java/) | Done |
| .NET web | [dotnet/](dotnet/) | Done |

## Portal (series)

The [10-code-control portal](../portal/) embeds examples **11–15** in tabs:

| Language | Entry | URL | Child port for 15 |
|----------|-------|-----|-------------------|
| Python | [../portal/python/](../portal/python/) | http://127.0.0.1:8100/?tab=15 | **8150** |
| Node.js | [../portal/node/](../portal/node/) | http://127.0.0.1:8101/?tab=15 | **8151** |
| Java | [../portal/java/](../portal/java/) | http://127.0.0.1:8102/?tab=15 | **8152** |
| .NET | [../portal/dotnet/](../portal/dotnet/) | http://127.0.0.1:8103/?tab=15 | **8153** |

See [../portal/README.md](../portal/README.md).

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
# or: cd node && npm start
# or: cd java && ./mvnw -q -DskipTests package && java -jar target/15-prerequisite-flags.jar
# or: cd dotnet && dotnet run --project 15-prerequisite-flags.csproj
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
