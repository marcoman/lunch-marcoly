# Java (web)

Java 21 web implementation of [13-flag-targeting-rules](../application.md).
The LaunchDarkly Java server SDK evaluates the public `team` context attribute;
No team omits that attribute.

## Run

```bash
./mvnw -q -DskipTests package
java -jar target/13-flag-targeting-rules.jar
```

Set `LD_SDK_KEY` for evaluation. Controls also require
`LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY`.
`PORT` defaults to `8080`.

Controls update flag on/off and fallthrough only. Provision the targeting rules
with the sibling [Terraform](../terraform/) or [REST](../rest/) example.
