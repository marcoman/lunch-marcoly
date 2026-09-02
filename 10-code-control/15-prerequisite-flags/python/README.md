# Python web — 15-prerequisite-flags

Python server-side SDK implementation of
[15-prerequisite-flags](../application.md).

Flag keys: `enable-grid-selection-highlight-prereq` (parent) and
`show-navigation-move-count-prereq` (child). They cite 11's highlight and
count flags; they do not share 11's inventory.

The server calls `variation_detail` for both the parent and dependent flags.
The lab rail shows each value and evaluation reason so an unmet dependency is
visible as `PREREQUISITE_FAILED`.

LaunchDarkly: **flag prerequisites**, **dependent flags**, and **evaluation
reasons** — [documentation](https://launchdarkly.com/docs/home/flags/prereqs).

## Run

```bash
export LD_SDK_KEY="sdk-..."
python 15-prerequisite-flags.py
```

Open http://127.0.0.1:8080/. Use `PORT` to select another port.

Provision first: [`../rest/create-flags.sh`](../rest/create-flags.sh).

For in-app controls, also set:

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
```

Controls can turn either flag on/off and change the parent fallthrough color.
They deliberately cannot edit the prerequisite relationship.

## API

```bash
curl "http://127.0.0.1:8080/api/flags?username=alice"
curl "http://127.0.0.1:8080/api/flag-controls"
```

Without `LD_SDK_KEY`, evaluation uses safe defaults: no highlight and no
count.
