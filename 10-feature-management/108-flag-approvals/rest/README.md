# REST

Create `show-navigation-move-count-approval`. The script does not turn the flag on. The page requests that approval.

Keywords: **feature flags** · **approvals**

Docs: [Create a feature flag](https://launchdarkly.com/docs/api/feature-flags/post-feature-flag)

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"   # optional, prints on/off
./create-flags.sh
```

`./delete-flag.sh` removes the flag.
