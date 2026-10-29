# REST — 22-api-progressive-rollout

These scripts create the highlight flag and start, read, or stop a **progressive environment release**.

Header on the release calls: `LD-API-Version: beta`.

[Environment releases (beta)](https://launchdarkly.com/docs/api/environment-releases)

## Scripts

| Script | Purpose |
|--------|---------|
| [create-flag.sh](create-flag.sh) | Create `api-progressive-grid-highlight` and leave it **off** |
| [start-progressive-release.sh](start-progressive-release.sh) | Turn the flag on, default rule `none`, `POST` the release |
| [get-progressive-release.sh](get-progressive-release.sh) | List newest progressive releases and the current step |
| [stop-progressive-release.sh](stop-progressive-release.sh) | Stop the active release. `back` (default) or `forward` |

`start-progressive-release.sh` does not send metrics. That is what makes the release progressive.

The phase clause is `user` / `kind` / `in` / `user`. A release on the default rule is rejected.

## Health check

Log in on the grid once before starting. The API returns `400` `health_checks_failed` when the flag has no recent evaluation for the `user` kind. `--bypass-health-checks` starts anyway.
