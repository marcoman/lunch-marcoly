# 17-scheduled-changes — Java console

Java 21 console for LaunchDarkly **scheduled flag changes**.

Keywords: **scheduled changes** · **feature flags** · **semantic patch**

Docs: [Scheduled flag changes](https://launchdarkly.com/docs/home/flags/scheduled-changes)

## Prerequisites

- Java 21+
- macOS or Linux terminal (`stty` provides raw mode)
- A LaunchDarkly Enterprise plan
- Flag provisioned by [REST](../rest/) or [Terraform](../terraform/)
- `LD_SDK_KEY` for evaluation
- `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY` for **G** / **T**

## Build and run

```bash
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"

cd 10-code-control/17-scheduled-changes/java-console
./mvnw -q -DskipTests package
java -jar target/17-scheduled-changes.jar
```

## Keys

| Key | Action |
|-----|--------|
| **G** | Start (replace pending, turn off, schedule on) |
| **T** | Stop (cancel pending and turn off); elapsed clock freezes |
| **M** | Cycle delay 1 → 2 → 5 → 10 minutes |
| **1** / **2** / **5** / **0** | Set 1, 2, 5, or 10 minutes |
| Arrows / WASD | Move |
| **L** | Logout |
| **Q** | Quit |

The clock is observational. Only the SDK evaluation can turn the selection green.
