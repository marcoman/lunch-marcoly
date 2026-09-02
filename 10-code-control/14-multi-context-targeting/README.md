# 14-multi-context-targeting

LaunchDarkly **multi-context** targeting for the lunch-marcoly grid navigator.

The web labs evaluate `show-partner-org-badge` against a
[multi-context](https://launchdarkly.com/docs/home/flags/multi-contexts):
**user** + **organization**. Provisioned AND [targeting rules](https://launchdarkly.com/docs/home/flags/target-rules)
serve `true` only for two pairs.

See [application.md](application.md) for the full specification.

Keywords: **multi-context** · **context kinds** · **targeting rules** · **feature flags**

## The 2×2

| User | Org | Partner badge |
|------|-----|----------------|
| `alice` | `acme` | yes |
| `alice` | `globex` | no |
| `bob` | `acme` | no |
| `bob` | `globex` | yes |

Same person, other company → no. Same company, other person → no. Org is **not**
a `user` attribute (that was [13](../13-flag-targeting-rules/)).

The labs use explicit **Alice / Bob** and **Acme / Globex** radio cards.
Its right rail keeps three things visible together as you walk the 2×2:

- the selected user and organization
- the exact JSON multi-context sent to LaunchDarkly
- current match status plus an event/evaluation history

## Provisioning

- [REST](rest/) creates the flag and the two AND rules.

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

The [10-code-control portal](../portal/) embeds examples **11–15** in tabs:

| Language | Entry | URL | Child port for 14 |
|----------|-------|-----|-------------------|
| Python | [../portal/python/](../portal/python/) | http://127.0.0.1:8100/?tab=14 | **8140** |
| Node.js | [../portal/node/](../portal/node/) | http://127.0.0.1:8101/?tab=14 | **8141** |
| Java | [../portal/java/](../portal/java/) | http://127.0.0.1:8102/?tab=14 | **8142** |
| .NET | [../portal/dotnet/](../portal/dotnet/) | http://127.0.0.1:8103/?tab=14 | **8143** |

See [../portal/README.md](../portal/README.md).

## Environment

```bash
export LD_SDK_KEY="sdk-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
export LD_API_ACCESS_TOKEN="api-..."
```

```bash
(cd rest && chmod +x *.sh && ./create-flags.sh)
cd python && python 14-multi-context-targeting.py
# or: (cd node && npm start)
# or: (cd java && ./mvnw -q -DskipTests package && java -jar target/14-multi-context-targeting.jar)
# or: (cd dotnet && dotnet run --project 14-multi-context-targeting.csproj)
```

Open http://127.0.0.1:8080/. Set `PORT` to override. Run one language at a time
on that port.

```bash
# Python console
cd python-console && python 14-multi-context-targeting.py

# Node console
cd node-console && npm install && npm start

# Java console
cd java-console && ./mvnw -q -DskipTests package && java -jar target/14-multi-context-targeting.jar

# C++ console
cd cpp && make && ./14-multi-context-targeting

# Go console
cd go && go build -o 14-multi-context-targeting . && ./14-multi-context-targeting

# Rust console
cd rust && cargo build --release && ./target/release/14-multi-context-targeting
```

## Collect results

Walks alice/bob × acme/globex (plus unmatched `carol`) and compares expected vs
SDK (or the running lab):

```bash
python collect-results.py
python collect-results.py --url http://127.0.0.1:8080
python collect-results.py --json
```
