# Python (web)

Request approval to turn on the move-count flag, then apply it after LaunchDarkly says the review passed.

## Run

From the repository root, with the virtualenv active:

```bash
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
cd 10-feature-management/108-flag-approvals/python
python 108-flag-approvals.py
```

Open [http://127.0.0.1:8180/](http://127.0.0.1:8180/). Create the flag first with [../rest/create-flags.sh](../rest/create-flags.sh). The environment must already require approvals.

## Where to look

| What you see | Where it is |
|--------------|-------------|
| Boolean read of the count flag | `evaluate_count` |
| Create the `turnFlagOn` request | `../approvals.py` `request_approval` |
| Apply after the review | `../approvals.py` `apply_approval` |

Keywords: **approvals** · **feature flags** · **boolean variations**

Docs: [Approvals](https://launchdarkly.com/docs/home/releases/approvals)
