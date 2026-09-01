# Portal (JavaScript)

Series shell for **30-client-sdk**: tabbed UI that embeds **31**, **32**, **33**, and **34**
JavaScript (browser SDK) examples.

| | Port |
|--|------|
| **Portal** | **8300** |
| **31 Client evaluation** | 8310 |
| **32 Identify** | 8320 |
| **33 Synced segments** | 8330 |
| **34 Twilio segments** | 8340 |

Keywords: **client-side SDK** · **client-side ID** · **series portal** · **iframe tabs**

Twins: [React](../react/) · [Vue](../vue/). Standalone `javascript/`
entrypoints still work without this shell.

## Prerequisites

- Node.js 20+
- `LD_CLIENT_SIDE_ID` (not `LD_SDK_KEY`) for the target environment
- Flags provisioned under each example
- Dependencies installed in all child examples:

```bash
for d in ../../31-client-evaluation/javascript \
         ../../32-client-identify/javascript \
         ../../33-synced-segments/javascript \
         ../../34-synced-segments-twilio/javascript; do
  (cd "$d" && npm install)
done
export LD_CLIENT_SIDE_ID="..."
```

Lab Controls still need `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and
`LD_ENVIRONMENT_KEY` on the child hosts (the portal only forwards the
environment).

## Run

```bash
cd 30-client-sdk/portal/javascript
npm start
```

Open [http://127.0.0.1:8300/](http://127.0.0.1:8300/). **Ctrl+C** stops the
portal and all children.

Override with `PORTAL_PORT`. The portal passes `PORT` to each child; solo apps
still default to **:8310** / **:8320** / **:8330** / **:8340** when run from their own
folders.

Series index: [../README.md](../README.md) · [../../README.md](../../README.md).
