# Go

Console application for [15-prerequisite-flags](../application.md). The Go
server SDK evaluates parent and child flags independently so an unmet
[prerequisite](https://launchdarkly.com/docs/home/flags/prereqs) shows up as
`PREREQUISITE_FAILED`.

## Prerequisites

- Go 1.22+
- Provisioned `-prereq` flags and `LD_SDK_KEY`

## Build and run

```bash
go mod tidy
go build -o 15-prerequisite-flags .
./15-prerequisite-flags
```

Login with a username. Flag changes refresh about every 500 ms. Count appears
only when the child variation is `true`. Press `L` to log out or `Q` to quit.
