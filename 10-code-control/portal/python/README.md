# Portal (Python)

Series shell for **10-code-control**: tabbed UI that embeds **11** flag enablement
and **12** flag variations side by side.

| | Port |
|--|------|
| **Portal** | **8100** |
| **11 Flag enablement** | 8110 |
| **12 Flag variations** | 8120 |

Keywords: **feature flags** · **boolean variations** · **contexts** · **series portal**

## Prerequisites

- Repository `.venv` activated
- `LD_SDK_KEY` for both tabs (flags provisioned under each example)

```bash
export LD_SDK_KEY="sdk-..."
```

## Run

```bash
cd 10-code-control/portal/python
python portal.py
```

Open [http://127.0.0.1:8100/](http://127.0.0.1:8100/). **Ctrl+C** stops the portal and both children.

Override with `PORTAL_PORT`. Solo apps still default to `:8080` when run from their own folders.
