# Java (web)

Java 21 web implementation of [14-multi-context-targeting](../application.md).
The LaunchDarkly Java server SDK evaluates `show-partner-org-badge` against a
[multi-context](https://launchdarkly.com/docs/home/flags/multi-contexts)
(`user` + `organization`).

## Run

```bash
./mvnw -q -DskipTests package
java -jar target/14-multi-context-targeting.jar
```

Set `LD_SDK_KEY` for evaluation. Controls also require
`LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY`.
`PORT` defaults to `8080`.

Controls update flag on/off and fallthrough only. Provision the targeting rules
with the sibling [REST](../rest/) example.

```bash
python ../collect-results.py --url http://127.0.0.1:8080
```
