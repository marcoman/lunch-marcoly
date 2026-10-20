# Java (web)

Java 21 web implementation of [15-prerequisite-flags](../application.md).
The LaunchDarkly Java server SDK evaluates parent and child flags independently
so an unmet [prerequisite](https://launchdarkly.com/docs/home/flags/prereqs)
shows up as `PREREQUISITE_FAILED`.

## Run

```bash
./mvnw -q -DskipTests package
java -jar target/15-prerequisite-flags.jar
```

Set `LD_SDK_KEY` for evaluation. Controls also require
`LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY`.
`PORT` defaults to `8080`.

Provision the `-prereq` flags with the sibling [REST](../rest/) example.
Controls never edit the prerequisite relationship.
