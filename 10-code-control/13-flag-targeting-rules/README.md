# 13-flag-targeting-rules

LaunchDarkly **targeting rules** for the lunch-marcoly grid navigator.

The web implementations evaluate `configure-team-label-style` against a public `team` [context attribute](https://launchdarkly.com/docs/home/flags/context-attributes). Provisioned [targeting rules](https://launchdarkly.com/docs/home/flags/target-rules) map Red, Blue, and Yellow teams to matching label styles; No team omits the attribute and receives `plain` fallthrough.

See [application.md](application.md) for the full specification.

## Targeting table

| Team context | Variation |
|--------------|-----------|
| `red` | `colored-red` |
| `blue` | `colored-blue` |
| `yellow` | `colored-yellow` |
| Omitted / unmatched | `plain` |
| Flag off | `plain` |

## Provisioning

- [Terraform](terraform/) provisions the flag, environment state, and all three rules.
- [REST](rest/) creates the flag and applies equivalent semantic-patch instructions.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| Python web | [python/](python/) | Done |
| Node.js web | [node/](node/) | Done |
| Java web | [java/](java/) | Done |
| .NET web | [dotnet/](dotnet/) | Done |

## Portal (series)

The [10-code-control portal](../portal/) embeds **11**, **12**, and **13** in tabs:

| Language | Entry | URL | Child port for 13 |
|----------|-------|-----|-------------------|
| Python | [../portal/python/](../portal/python/) | http://127.0.0.1:8100/ | **8130** |
| Node.js | [../portal/node/](../portal/node/) | http://127.0.0.1:8101/ | **8131** |
| Java | [../portal/java/](../portal/java/) | http://127.0.0.1:8102/ | **8132** |
| .NET | [../portal/dotnet/](../portal/dotnet/) | http://127.0.0.1:8103/ | **8133** |

See [../portal/README.md](../portal/README.md).

## Environment

```bash
export LD_SDK_KEY="sdk-..."
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="test"
export LD_API_ACCESS_TOKEN="api-..." # lab Controls and rest/
```

Run (each listens on http://127.0.0.1:8080/ by default):

```bash
# Python
cd python && python 13-flag-targeting-rules.py

# Node
cd node && npm install && npm start

# Java
cd java && ./mvnw -q -DskipTests package && java -jar target/13-flag-targeting-rules.jar

# .NET
cd dotnet && dotnet run
```

See each language folder’s README for toolchain notes.