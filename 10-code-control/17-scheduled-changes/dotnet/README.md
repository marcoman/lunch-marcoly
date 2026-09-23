# 17-scheduled-changes — .NET web

Schedule a LaunchDarkly flag to turn the grid highlight on after a short delay.

## Prerequisites

- .NET **10+**
- A LaunchDarkly Enterprise plan
- Flag provisioned by [REST](../rest/) or [Terraform](../terraform/)
- `LD_SDK_KEY` for SDK evaluation
- `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY` for the
  schedule controls

## Run

```bash
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"

cd 10-code-control/17-scheduled-changes/dotnet
dotnet run
```

Open [http://127.0.0.1:8173/](http://127.0.0.1:8173/). `PORT` overrides the
default.

Choose a delay (one minute minimum) and start. Starting again replaces pending
changes for this dedicated flag. The lab resets the flag off with a semantic
patch, schedules `turnFlagOn`, and displays elapsed time plus the scheduled
wall time.

The second button stops the demo. It reads **Stop schedule** while a change is
pending and **Turn flag off** after the change has been applied; both cancel
every pending change and turn the flag off. The elapsed clock then holds its
last value until you start a new schedule.

The elapsed clock is observational. Only the LaunchDarkly flag evaluation can
turn the selection green.

## Why the highlight lags the delay

A one-minute schedule often turns green near 1:30. LaunchDarkly executes close
to the execution date rather than exactly on it, the change still has to reach
this server's SDK stream, and the page re-evaluates only every two seconds. The
panel reports the elapsed time at which `green` first appeared so the lag is
visible.

See the [scheduled changes documentation](https://launchdarkly.com/docs/home/flags/scheduled-changes).
