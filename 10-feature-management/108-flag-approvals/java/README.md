# Java (web)

Request approval to turn on the move-count flag, then apply it after LaunchDarkly says the review passed.

Keywords: **approvals** · **feature flags** · **boolean variations**

Docs: [Approvals](https://launchdarkly.com/docs/home/releases/approvals)

## Run

```bash
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
cd 10-feature-management/108-flag-approvals/java
./mvnw -q -DskipTests package
java -jar target/108-flag-approvals.jar
```

Open [http://127.0.0.1:8182/](http://127.0.0.1:8182/). Create the flag first with [../rest/create-flags.sh](../rest/create-flags.sh). The environment must already require approvals.

## Where to look

| What you see | Where it is |
|--------------|-------------|
| Boolean read of the count flag | `FlagCount.evaluate` |
| Create the `turnFlagOn` request | `Approvals.requestApproval` |
| Apply after the review | `Approvals.apply` |
