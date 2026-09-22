# TODO

Work queue for new lunch-marcoly examples. Ship in this order.

## Next

| Priority | Example | Series | Status |
|----------|---------|--------|--------|
| 1 | [17-scheduled-changes](10-code-control/17-scheduled-changes/) | 10-code-control | **Next** (stub) |
| 2 | [35-client-bootstrap](30-client-sdk/35-client-bootstrap/) | 30-client-sdk | Stub |
| 3 | [36-client-track-events](30-client-sdk/36-client-track-events/) | 30-client-sdk | Stub |

[16-percentage-rollout](10-code-control/16-percentage-rollout/) is **done** (web + consoles + REST/Terraform). It is a **static** percentage (for example 30% highlighted). It is not a time-ramped progressive rollout ([99-use-cases/14-progressive-rollout](99-use-cases/14-progressive-rollout/)) and not the A-B-C-D experiment ([99-use-cases/01-abcd-test](99-use-cases/01-abcd-test/)). Dedicated flag keys keep 11 independent.

Other stubs already in the tree: [41-no-sdk-singleton](40-dont-do-this/41-no-sdk-singleton/), [42-local-if-no-sdk](40-dont-do-this/42-local-if-no-sdk/), [99-use-cases/17-migration-flags](99-use-cases/17-migration-flags/).

## Don't do

| Idea | Why not |
|------|---------|
| **26-offline-evaluation** (AgentControl) | Name collides with SDK offline mode. The fixture / side-by-side prompt idea was declined. **Don't do.** |
| **37-client-offline-mode** (client SDK) | Server fallbacks already live in [18-sdk-fallbacks](99-use-cases/18-sdk-fallbacks/). Client airplane-mode is a weak classroom demo. **Don't do.** |

Do not create folders for those two.

## Notes

- 10-series **16** is percentage rollout, not migration flags. Migration remains [99-use-cases/17-migration-flags](99-use-cases/17-migration-flags/).
- 20-series next number stays **26** only if a later AgentControl lesson is approved under a different name. **25-agent-graph** is in.
- Client bootstrap folder is `35-client-bootstrap`, not `bootstrapRender`.
- Track events: `login_completed` + `grid_move` only unless `cell_selected` is specified later.
