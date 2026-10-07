# TODO

Work queue for new lunch-marcoly examples. Ship in this order.

## Next

30-client-sdk **31–36** are in. Remaining stubs:

- [41-no-sdk-singleton](40-dont-do-this/41-no-sdk-singleton/)
- [42-local-if-no-sdk](40-dont-do-this/42-local-if-no-sdk/)
- [99-use-cases/17-migration-flags](99-use-cases/17-migration-flags/)
- [99-use-cases/20-multi-arm-bandit](99-use-cases/20-multi-arm-bandit/) — grid bandit; not `53-mobile-experiment`
- [20-agent-config/20-capstone](20-agent-config/20-capstone/) — unnumbered. One Node app composes graph, tools, judges, and feedback. `21`–`25` stay as they are. English and Spanish live here. Later `27`, `28`, … roll in

## Don't do

| Idea | Why not |
|------|---------|
| **26-offline-evaluation** (AgentControl) | Name collides with SDK offline mode. The fixture / side-by-side prompt idea was declined. **Don't do.** |
| **37-client-offline-mode** (client SDK) | Server fallbacks already live in [18-sdk-fallbacks](99-use-cases/18-sdk-fallbacks/). Client airplane-mode is a weak classroom demo. **Don't do.** |

Do not create folders for those two.

## Notes

- 10-series **16** is percentage rollout, not migration flags. Migration remains [99-use-cases/17-migration-flags](99-use-cases/17-migration-flags/).
- 20-series **26** is [26-flags-vs-agent-control](20-agent-config/26-flags-vs-agent-control/). Next AgentControl number is **27**. [20-capstone](20-agent-config/20-capstone/) does not consume that number. The image / essay / animal apps stay **70-model-demos**.
- **70-model-demos** children are `01`, `02`, `03`, `04` inside that folder. `04-terraform-codegen` is Python **:8740**. **80** stays the next free decade.
- Client bootstrap folder is `35-client-bootstrap`, not `bootstrapRender`.
- Track events: `login_completed` + `grid_move` only unless `cell_selected` is specified later.
