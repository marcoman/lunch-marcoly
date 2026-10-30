# 106-percentage-rollout

LaunchDarkly **percentage rollout** for the grid navigator: gradually expose
a highlighted cell to a **fixed** share of users. Assignment is sticky on the
username **context key**.

This is **not** [14-progressive-rollout](../../99-use-cases/14-progressive-rollout/)
(time-staged 10→100%). The same climb, started with the environment releases beta API, is
[22-api-progressive-rollout](../../99-use-cases/22-api-progressive-rollout/). This is **not**
[01-abcd-test](../../99-use-cases/01-abcd-test/) (four experiment labels).
The AgentControl sticky split that buckets by `team` is the stub
[29-team-rollout](../../20-agent-config/29-team-rollout/).

Keywords: **percentage rollout** · **context key** · **sticky bucketing** ·
**feature flags**

Docs: [Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts)

Each web drawer includes **Code Example** before **About**. It shows the real
user context, variation-detail evaluation, and response fields—including the
variation index and evaluation reason—in Python, Node.js, Java, or .NET.

## Intended aha

Log in as `alice`, then click through `alice1`, `alice2`, and so on until the
history shows both rollout sides. Click an older name to prove its assignment
does not flip while configuration is unchanged. The dashboard shows a static
percentage on the default rule (lab default **30%** `green` / **70%** `none`).

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| Python web | [python/](python/) | Done — standalone **:8160**, Python portal tab 106 |
| Node web | [node/](node/) | Done — standalone **:8080**, Node portal tab 106 **:8161** |
| Java web | [java/](java/) | Done — standalone **:8080**, Java portal tab 106 **:8162** |
| .NET web | [dotnet/](dotnet/) | Done — standalone **:8080**, .NET portal tab 106 **:8163** |
| Python console | [python-console/](python-console/) | Done — **N** / **P** walk `<login>`, `<login>1`, `<login>2`, … |
| Node console | [node-console/](node-console/) | Done |
| Java console | [java-console/](java-console/) | Done |
| Go console | [go/](go/) | Done |
| Rust console | [rust/](rust/) | Done |
| C++ console | [cpp/](cpp/) | Done |

Provision with [REST](rest/) or [Terraform](terraform/). See
[application.md](application.md) for the full contract.

## Start a percentage rollout

The **About** tab in the right drawer links to this flag's targeting page. For this
lab that page is:

[enable-grid-selection-highlight-pct targeting](https://app.launchdarkly.com/projects/lunch-marcoly/flags/enable-grid-selection-highlight-pct/targeting?env=production&selected-env=production)

The app builds the same URL from `LD_PROJECT_KEY` and `LD_ENVIRONMENT_KEY`.
Restart the server after you export them. The Grid tab already shows the
context that was sent and the variation that came back.

On the targeting page:

1. Turn the flag **on**.
2. Edit the **default rule** and choose a percentage rollout.
3. Give `green` a share and `none` the rest. The two shares add up to 100.
   This lab starts at **30% green / 70% none**.
4. Bucket by the **user** context key. That key is the username.
5. Save the targeting.
6. Return to the grid. Evaluate a few usernames. Open an older name to see
   that its variation stayed put.

Docs: [Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts)

## REST scripts

`rest/create-flag.sh` creates the flag, then calls `set-rollout-percent.sh 30`.

`rest/set-rollout-percent.sh <green-percent>` turns the flag on and replaces
the default-rule weights immediately. The argument is the `green` share, from
0 to 100. The remainder is `none`. Bucketing uses the `user` context key.
LaunchDarkly stores each share in thousandths, so 30% is weight `30000`. The
script does not create a schedule and does not move the weights later.

`rest/get-rollout.sh` is read-only. It prints whether the flag is on in
`LD_ENVIRONMENT_KEY`, which context kind the default rule buckets by, and each
variation's percent.

```bash
./set-rollout-percent.sh 30
./get-rollout.sh
```

## Quick start

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
(cd rest && ./create-flag.sh)

export LD_SDK_KEY="sdk-..."
cd python
python 106-percentage-rollout.py
```

Open [http://127.0.0.1:8160/](http://127.0.0.1:8160/), or run the Python
[portal](../portal/) and select tab 106. Open **About** in the right drawer for the targeting link and the steps above.

Consoles: Python / Node / Java / Go / Rust / C++. Press **N** / **P** to walk
generated usernames.
