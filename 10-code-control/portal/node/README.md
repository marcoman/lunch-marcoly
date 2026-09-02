# Portal (Node)

Series shell for **10-code-control**: tabbed UI that embeds **11–14** side by side.

| | Port |
|--|------|
| **Portal** | **8101** |
| **11 Flag enablement** | 8111 |
| **12 Flag variations** | 8121 |
| **13 Flag targeting rules** | 8131 |
| **14 Multi-context targeting** | 8141 |

Keywords: **feature flags** · **targeting rules** · **contexts** · **series portal**

## Prerequisites

- Node.js 20+
- `LD_SDK_KEY` (flags provisioned under each example)
- Dependencies installed in all child examples:

```bash
for d in ../../11-flag-enablement/node ../../12-flag-variations/node ../../13-flag-targeting-rules/node ../../14-multi-context-targeting/node; do
  (cd "$d" && npm install)
done
export LD_SDK_KEY="sdk-..."
```

## Run

```bash
cd 10-code-control/portal/node
npm start
```

Open [http://127.0.0.1:8101/](http://127.0.0.1:8101/). **Ctrl+C** stops the portal and all children.

Override with `PORTAL_PORT`. The portal passes `PORT` to each child; solo apps
still default to `:8080` when run from their own folders.

Twins: [Python](../python/) · [Java](../java/) · [.NET](../dotnet/). Series index: [../README.md](../README.md).
