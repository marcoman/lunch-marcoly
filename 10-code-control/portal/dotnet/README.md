# Portal (.NET)

One-command .NET shell for **10-code-control** examples **11–15**. It serves iframe
tabs, starts each Minimal API child, and stops them on Ctrl+C.

| Process | Port |
|---------|------|
| Portal | **8103** |
| 11 Flag enablement | **8113** |
| 12 Flag variations | **8123** |
| 13 Flag targeting rules | **8133** |
| 14 Multi-context targeting | **8143** |
| 15 Prerequisite flags | **8153** |

## Prerequisites

```bash
export PATH="/usr/local/share/dotnet:$PATH"
export LD_SDK_KEY="sdk-..."
```

For the in-app Controls tabs, also export `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY`.

## Run

```bash
cd 10-code-control/portal/dotnet
dotnet run
```

Open [http://127.0.0.1:8103/](http://127.0.0.1:8103/). Override the portal with `PORTAL_PORT`. Children inherit the environment and receive their assigned `PORT`.

Twins: [Python](../python/) · [Node](../node/) · [Java](../java/). Series index: [../README.md](../README.md).
