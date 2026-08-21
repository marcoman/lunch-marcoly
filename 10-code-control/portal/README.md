# 10-code-control portal

One-command shells that embed **11-flag-enablement** and **12-flag-variations** in
tabbed iframes — same idea as the [20-agent-config portal](../../20-agent-config/portal/).

| Language | Entry | Portal port | Child ports |
|----------|-------|-------------|-------------|
| **Python** | [`python/`](python/) | **8100** | 8110 (11) · 8120 (12) |

Node / Java / .NET portals can follow the same pattern later.

Keywords: **feature flags** · **series portal** · **iframe tabs**

## Run (Python)

```bash
export LD_SDK_KEY="sdk-..."
cd 10-code-control/portal/python && python portal.py
# → http://127.0.0.1:8100/
```
