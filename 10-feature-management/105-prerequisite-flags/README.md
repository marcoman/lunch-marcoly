# 105-prerequisite-flags

LaunchDarkly **flag prerequisites** for the lunch-marcoly grid navigator.

Two dependents, `show-navigation-move-count-prereq` and
`show-anonymous-host-os-emoji-prereq`, evaluate normally only when their parent
`enable-grid-selection-highlight-prereq` flag is **on** and serving
**`green`**. Otherwise each child serves its off variation and reports
`PREREQUISITE_FAILED`. Turning the parent off hides both the count and the
host emoji. That is the point: one parent, two children.

The four-reason tour (`PREREQUISITE_FAILED`, `RULE_MATCH`, `FALLTHROUGH`,
`ERROR`) is the stub [109-evaluation-reasons](../109-evaluation-reasons/).

These keys cite [101-flag-enablement](../101-flag-enablement/) but are **not**
11's flags, so 11's independent count toggle is unchanged.

See [application.md](application.md) for the full specification.

Keywords: **prerequisites** · **dependent flag** · **off variation** ·
**evaluation reasons**

Docs: [Flag prerequisites](https://launchdarkly.com/docs/home/flags/prereqs)

The web apps explain this on the **About** tab in the right drawer. The
**Prerequisite** tab shows both variations, the context, and the controls.
**Code Example**, immediately before About, shows that the application always
evaluates the parent and both child flags and lets LaunchDarkly enforce each
prerequisite.

## The dependency

```text
enable-grid-selection-highlight-prereq = green
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
show-navigation-move-count   show-anonymous-host-os-emoji
         = true                       = true
```

| Parent | Count child | Emoji child | Result |
|--------|-------------|-------------|--------|
| On → `green` | On → `true` | On → `true` | Green highlight, Count, and host emoji |
| Off → `none` | On → `true` | On → `true` | No highlight, no Count, no emoji |
| On → `yellow` | On → `true` | On → `true` | Yellow highlight, no Count, no emoji |
| On → `green` | Off → `false` | On → `true` | Green highlight and emoji, no Count |

The application always asks the SDK for all three variations. It does not
implement either dependency with application branching. The emoji flag cites
[102-flag-variations](../102-flag-variations/) `show-anonymous-host-os-emoji`.
This lab evaluates it on the same user context. Anonymous context stays in 102.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| Python web | [python/](python/) | Done |
| Node.js web | [node/](node/) | Done |
| Java web | [java/](java/) | Done |
| .NET web | [dotnet/](dotnet/) | Done |
| Python console | [python-console/](python-console/) | Done |
| Node.js console | [node-console/](node-console/) | Done |
| Java console | [java-console/](java-console/) | Done |
| C++ console | [cpp/](cpp/) | Done |
| Go console | [go/](go/) | Done |
| Rust console | [rust/](rust/) | Done |

## Portal (series)

The [10-feature-management portal](../portal/) embeds examples **11–15** in tabs:

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
cd python && python 105-prerequisite-flags.py
# or: cd node && npm start
# or: cd java && ./mvnw -q -DskipTests package && java -jar target/105-prerequisite-flags.jar
# or: cd dotnet && dotnet run --project 105-prerequisite-flags.csproj
```

Provisioning: [REST](rest/) creates the three `-prereq` flags and attaches
the same parent prerequisite to both children. In-app Controls still cannot
edit that relationship. Re-run `create-flags.sh` on an existing project to add
the emoji child.

## Run

```bash
cd python
python 105-prerequisite-flags.py
```

Open http://127.0.0.1:8080/. Set `PORT` to override.

## Dedicated keys

| Role | 105 key | Cites 101 key |
|------|--------|----------------|
| Parent | `enable-grid-selection-highlight-prereq` | `enable-grid-selection-highlight` (101) |
| Child | `show-navigation-move-count-prereq` | `show-navigation-move-count` (101) |
| Child | `show-anonymous-host-os-emoji-prereq` | `show-anonymous-host-os-emoji` (102) |
