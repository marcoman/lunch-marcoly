# Python web — 24-multitenant-datacenter

First presentation for [24-multitenant-datacenter](../application.md).

The floor draws six datacenters. Shared replicas are named for the region (`usw1-1`, `use1-1`). `us-east-1` also has `use1-3`. Named customers are ACME, ENZO, BIGCO, DREX, HUDSON, RHEIN, and KOPI. The three large customers have one replica. ENZO keeps two.

Copy [customizations.json.example](../customizations.json.example) to `customizations.json` to override the shared replica icon or the customer icon array. Icons in that file are paths inside this example. A `customizations/` folder next to it is for a local replacement and is gitignored. Without the local file, the page uses the example icons. Security, firewall, data sharing, and marketing are icons on every size row. Faint is not deployed, grey is deployed and off, and color is on. The Rolling deployments tab walks one datacenter at a time, 1 second between replicas. The Flags tab writes targeting rules when `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY` are set. Click a size row to evaluate that multi-context. Evaluation needs `LD_SDK_KEY`. Create the six flags and `mtdc-gdpr-eu` with [../rest/create-all.sh](../rest/create-all.sh) before the first run in a new project.

Feature flags — targeting rules
https://launchdarkly.com/docs/home/flags/targeting-rules

Feature flags — multi-contexts
https://launchdarkly.com/docs/home/flags/multi-contexts

```bash
python 24-multitenant-datacenter.py
```

Open http://127.0.0.1:8788/ . `PORT` overrides the listen port.

[Multi-contexts](https://launchdarkly.com/docs/home/flags/multi-contexts)
