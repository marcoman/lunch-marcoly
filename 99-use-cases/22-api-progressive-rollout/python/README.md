# Python web — 22-api-progressive-rollout

Grid navigator for [22-api-progressive-rollout](../application.md).

The page evaluates `api-progressive-grid-highlight`. **Start progressive release** on the Release tab POSTs the environment release. [../rest/start-progressive-release.sh](../rest/start-progressive-release.sh) sends the same body.

```bash
python 22-api-progressive-rollout.py
```

Open http://127.0.0.1:8780/ . `PORT` overrides the listen port.

```bash
python 22-api-progressive-rollout.py --evaluate-once alice
```

[Environment releases (beta)](https://launchdarkly.com/docs/api/environment-releases)
