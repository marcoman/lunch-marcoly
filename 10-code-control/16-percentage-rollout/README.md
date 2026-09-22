# 16-percentage-rollout

LaunchDarkly **percentage rollout** for the grid navigator: gradually expose
a highlighted cell to a **fixed** share of users. Assignment is sticky on the
username **context key**.

This is **not** [14-progressive-rollout](../../99-use-cases/14-progressive-rollout/)
(time-staged 10→100%). This is **not**
[01-abcd-test](../../99-use-cases/01-abcd-test/) (four experiment labels).

Keywords: **percentage rollout** · **context key** · **sticky bucketing** ·
**feature flags**

Docs: [Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts)

## Intended aha

Log in as `alice`, then click through `alice1`, `alice2`, and so on until the
history shows both rollout sides. Click an older name to prove its assignment
does not flip while configuration is unchanged. The dashboard shows a static
percentage on the default rule (lab default **30%** `green` / **70%** `none`).

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| Python web | [python/](python/) | Done — standalone **:8160**, Python portal tab 16 |
| Node web | [node/](node/) | Done — standalone **:8080**, Node portal tab 16 **:8161** |
| Java web | [java/](java/) | Done — standalone **:8080**, Java portal tab 16 **:8162** |
| .NET web | [dotnet/](dotnet/) | Done — standalone **:8080**, .NET portal tab 16 **:8163** |
| Python console | [python-console/](python-console/) | Done — **N** / **P** walk `<login>`, `<login>1`, `<login>2`, … |
| Node console | [node-console/](node-console/) | Done |
| Java console | [java-console/](java-console/) | Done |
| Go console | [go/](go/) | Done |
| Rust console | [rust/](rust/) | Done |
| C++ console | [cpp/](cpp/) | Done |

Provision with [REST](rest/) or [Terraform](terraform/). See
[application.md](application.md) for the full contract.

## Quick start

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
(cd rest && ./create-flag.sh)

export LD_SDK_KEY="sdk-..."
cd python
python 16-percentage-rollout.py
```

Open [http://127.0.0.1:8160/](http://127.0.0.1:8160/), or run a
[portal](../portal/) and select tab 16.

Consoles: Python / Node / Java / Go / Rust / C++. Press **N** / **P** to walk
generated usernames.
