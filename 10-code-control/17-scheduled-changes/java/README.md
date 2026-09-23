# 17-scheduled-changes — Java web

Java 21 web implementation of [17-scheduled-changes](../application.md).

Keywords: **scheduled changes** · **feature flags** · **semantic patch** ·
**contexts**

Docs: [Scheduled flag changes](https://launchdarkly.com/docs/home/flags/scheduled-changes) ·
[Scheduled changes API](https://launchdarkly.com/docs/api/scheduled-changes)

## Prerequisites

- Java **21+**
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

cd 10-code-control/17-scheduled-changes/java
./mvnw -q -DskipTests package
java -jar target/17-scheduled-changes.jar
```

Open [http://127.0.0.1:8172/](http://127.0.0.1:8172/). `PORT` overrides the
default.

Choose a delay from one to ten minutes and start. Starting again replaces all
pending changes for this dedicated flag, immediately resets the flag off with
a semantic `turnFlagOff` patch, and schedules `turnFlagOn`.

The second button reads **Stop schedule** while a change is pending and
**Turn flag off** after it applies. Both actions delete pending changes and
turn the flag off. The elapsed clock freezes when stopped and resets on start.

## Why the highlight can lag

A one-minute schedule often turns green near 1:30. LaunchDarkly executes close
to the execution date rather than exactly on it, the update must reach the
server SDK stream, and the browser re-evaluates only every two seconds. The UI
shows when green was first observed so that lag remains visible.
