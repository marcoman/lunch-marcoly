# Portal (Node)

Series shell for **10-code-control**: tabbed UI that embeds **11** flag enablement
and **12** flag variations side by side.

| | Port |
|--|------|
| **Portal** | **8101** |
| **11 Flag enablement** | 8111 |
| **12 Flag variations** | 8121 |

Keywords: **feature flags** · **boolean variations** · **contexts** · **series portal**

## Prerequisites

- Node.js 20+
- `LD_SDK_KEY` for both tabs (flags provisioned under each example)
- Dependencies installed in both child examples:

```bash
for d in ../../11-flag-enablement/node ../../12-flag-variations/node; do
  (cd "$d" && npm install)
done
export LD_SDK_KEY="sdk-..."
```

## Run

```bash
cd 10-code-control/portal/node
npm start
```

Open [http://127.0.0.1:8101/](http://127.0.0.1:8101/). **Ctrl+C** stops the portal and both children.

Override with `PORTAL_PORT`. The portal passes `PORT` to each child; solo apps
still default to `:8080` when run from their own folders.
