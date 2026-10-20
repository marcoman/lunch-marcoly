# Portal (Python)

Series shell for **10-code-control**: tabbed UI that embeds **101–107** side by side.

| | Port |
|--|------|
| **Portal** | **8100** |
| **101 Flag enablement** | 8110 |
| **102 Flag variations** | 8120 |
| **103 Flag targeting rules** | 8130 |
| **104 Multi-context targeting** | 8140 |
| **105 Prerequisite flags** | 8150 |
| **106 Percentage rollout** | 8160 |
| **107 Scheduled changes** | 8170 |

Keywords: **feature flags** · **targeting rules** · **contexts** · **series portal**

## Prerequisites

- Repository `.venv` activated
- `LD_SDK_KEY` (flags provisioned under each example)
- For tab 17 controls: `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and
  `LD_ENVIRONMENT_KEY`

```bash
export LD_SDK_KEY="sdk-..."
```

## Run

```bash
cd 10-code-control/portal/python
python portal.py
```

Open [http://127.0.0.1:8100/](http://127.0.0.1:8100/). **Ctrl+C** stops the portal and all children.

Override with `PORTAL_PORT`. Solo apps use the standalone default documented in
their own README.

Twins: [Node](../node/) · [Java](../java/) · [.NET](../dotnet/). Series index: [../README.md](../README.md).
