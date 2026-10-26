# Tenant datacenters

Python web lab for [21-tenant-datacenters](../README.md). Each tenant presence
is one context. The page evaluates `tenant-border-palette`,
`tenant-box-fill`, `tenant-security`, and `tenant-firewall` for every box. Security waves
release the lock by name, by datacenter for Large, or as a full deployment.
`tenant-firewall` draws an icon when the flag is true.

Feature flags — multivariate variations
https://launchdarkly.com/docs/home/flags/variations

## Run

```bash
pip install -r requirements.txt
export LD_SDK_KEY="sdk-..."
python 21-tenant-datacenters.py
```

Open http://127.0.0.1:8080/. Set `PORT` to override.

Without `LD_SDK_KEY`, the border stays the hairline and the boxes stay empty.
The Toggles tab also needs `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and
`LD_ENVIRONMENT_KEY`. Create the flags and segments with
[../rest/create-all.sh](../rest/create-all.sh) in the same environment as the
SDK key.

Company name and logo come from `../customizations.json` when that file
exists, and from `../customizations.json.example` otherwise.
