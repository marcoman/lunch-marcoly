# .NET (web)

Web application version of the [00-reference-code grid navigator](../application.md). **No LaunchDarkly** — this is the baseline for the code-control examples.

## Prerequisites

- **.NET SDK 10**
- A modern browser

If `dotnet` is not already on `PATH`:

```bash
export PATH="/usr/local/share/dotnet:$PATH"
dotnet --list-sdks   # expect 10.x
```

On Windows, install [.NET SDK 10](https://dotnet.microsoft.com/download) and ensure `dotnet` is on `PATH`. With WSL, build and run inside WSL.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `8080` | HTTP listen port |

## Build

```bash
export PATH="/usr/local/share/dotnet:$PATH"
dotnet build
```

## Run

```bash
dotnet run
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/). Press Ctrl+C to stop.

## What to expect

1. Enter a username on the login screen (empty names are rejected).
2. The grid shows your name, current position (`m/m` initially), and previous position (`—`).
3. Use arrow keys or WASD to move; the selected cell shows **X** with no color highlight.
4. Movement stops at grid edges.
