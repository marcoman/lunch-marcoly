# Portal (Python)

Series shell for **10-code-control**: tabbed UI that embeds **11**, **12**, and **13**
side by side.

| | Port |
|--|------|
| **Portal** | **8100** |
| **11 Flag enablement** | 8110 |
| **12 Flag variations** | 8120 |
| **13 Flag targeting rules** | 8130 |

Keywords: **feature flags** · **targeting rules** · **contexts** · **series portal**

## Prerequisites

- Repository `.venv` activated
- `LD_SDK_KEY` (flags provisioned under each example)

```bash
export LD_SDK_KEY="sdk-..."
```

## Run

```bash
cd 10-code-control/portal/python
python portal.py
```

Open [http://127.0.0.1:8100/](http://127.0.0.1:8100/). **Ctrl+C** stops the portal and all children.

Override with `PORTAL_PORT`. Solo apps still default to `:8080` when run from their own folders.

Twins: [Node](../node/) · [Java](../java/) · [.NET](../dotnet/). Series index: [../README.md](../README.md).
