# REST provisioning — 17-scheduled-changes

Create the dedicated string flag, configure `green` as its on fallthrough, and
leave it off so the first scheduled run has a visible change.

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"

./create-flag.sh
```

The Python UI uses the same three variables to list, delete, and create
**scheduled changes**. Starting again deletes every pending change for this
dedicated flag, resets the flag off, and schedules one `turnFlagOn`
instruction.

Scheduled flag changes require a LaunchDarkly **Enterprise** plan.

Docs: [Scheduled flag changes](https://launchdarkly.com/docs/home/flags/scheduled-changes) ·
[Scheduled changes API](https://launchdarkly.com/docs/api/scheduled-changes)
