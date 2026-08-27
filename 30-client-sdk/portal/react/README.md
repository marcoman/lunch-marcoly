# Portal (React)

Series shell for **30-client-sdk**: tabbed UI that embeds **31**, **32**, and **33**
React Web SDK examples.

| | Port |
|--|------|
| **Portal** | **8301** |
| **31 Client evaluation** | 8311 |
| **32 Identify** | 8321 |
| **33 Synced segments** | 8331 |

Keywords: **client-side SDK** · **React Web SDK** · **client-side ID** · **series portal** · **iframe tabs**

Twins: [JavaScript](../javascript/) · [Vue](../vue/). Standalone `react/`
entrypoints still work without this shell.

## Prerequisites

- Node.js 20+
- `LD_CLIENT_SIDE_ID` (not `LD_SDK_KEY`) for the target environment
- Flags provisioned under each example
- Dependencies installed in all child examples (Vite must be present):

```bash
for d in ../../31-client-evaluation/react \
         ../../32-client-identify/react \
         ../../33-synced-segments/react; do
  (cd "$d" && npm install)
done
export LD_CLIENT_SIDE_ID="..."
```

Lab Controls still need `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and
`LD_ENVIRONMENT_KEY` on the child hosts (the portal only forwards the
environment).

## Run

```bash
cd 30-client-sdk/portal/react
npm start
```

Open [http://127.0.0.1:8301/](http://127.0.0.1:8301/). **Ctrl+C** stops the
portal and all children.

Override with `PORTAL_PORT`. The portal passes `PORT` to each Vite child; solo
apps still default to **:8311** / **:8321** / **:8331** when run from their own
folders.

Series index: [../README.md](../README.md) · [../../README.md](../../README.md).
