# TODO

Work queue for new lunch-marcoly examples. Ship in this order.

## Next

30-client-sdk **31–36** are in. Remaining stubs:

- [41-no-sdk-singleton](40-dont-do-this/41-no-sdk-singleton/)
- [42-local-if-no-sdk](40-dont-do-this/42-local-if-no-sdk/)
- [99-use-cases/17-migration-flags](99-use-cases/17-migration-flags/)
- [99-use-cases/20-multi-arm-bandit](99-use-cases/20-multi-arm-bandit/) — grid bandit; not `53-mobile-experiment`
- [20-agent-config/20-capstone](20-agent-config/20-capstone/) — unnumbered. Python **:8290**, Node **:8291**, Java **:8292**, .NET **:8293** built, not in the portal. Graph is assess → specialist → finalize. Checked tools (Pig Latin, ROT13, joke tagline) run after the draft and before finalize. Judges and feedback stay on the draft. `21`–`25` stay as they are. English and Spanish live here. Later lessons keep their own numbers and do not roll into the capstone.

New stubs (README only, not built):

- [18-flag-approvals](10-code-control/18-flag-approvals/) — approval to turn the move-count flag on. Ports **:8180–:8183** when built.
- [19-evaluation-reasons](10-code-control/19-evaluation-reasons/) — `PREREQUISITE_FAILED`, `RULE_MATCH`, `FALLTHROUGH`, `ERROR` on screen. Ports **:8190–:8193** when built.
- [segment-targeting](10-code-control/segment-targeting/) — included-targets segment, server SDK. Unnumbered: **18** and **19** fill the decade, and **20** is AgentControl. Read this before [33-synced-segments](30-client-sdk/33-synced-segments/).
- [27-agent-mode](20-agent-config/27-agent-mode/) — agent mode only, one instructions value. Does not roll into the capstone. Ports **:8270–:8273**.
- [28-context-attributes](20-agent-config/28-context-attributes/) — region and audience select a variation. Not `{{ }}` prompt variables. Ports **:8280–:8283**.
- [29-team-rollout](20-agent-config/29-team-rollout/) — sticky percentage rollout bucketed by `team`. Not [14-progressive-rollout](99-use-cases/14-progressive-rollout/). Do not use ports **:8290–:8293** (capstone).
- [37-client-evaluation-details](30-client-sdk/37-client-evaluation-details/) — client `variationDetail()` next to `variation()`.
- [38-client-secure-mode](30-client-sdk/38-client-secure-mode/)
- [39-client-context-cache](30-client-sdk/39-client-context-cache/) — local storage cache, called out in the UI. Not [35-client-bootstrap](30-client-sdk/35-client-bootstrap/).
- [55-automatic-environment-attributes](50-mobile/55-automatic-environment-attributes/)
- [56-mobile-multi-environment](50-mobile/56-mobile-multi-environment/)
- [63-server-errors](60-observability/63-server-errors/) — one deliberate error, visible as an error and a log line. **64** stays free.
- [65-server-metrics](60-observability/65-server-metrics/) — custom metric. [62-server-traces](60-observability/62-server-traces/) is spans only.
- [01-image-processing](70-model-demos/01-image-processing/), [02-text-origin](70-model-demos/02-text-origin/), [03-guess-the-animal](70-model-demos/03-guess-the-animal/) — plan these next to [04-terraform-codegen](70-model-demos/04-terraform-codegen/). Not a new decade.

## Don't do

| Idea | Why not |
|------|---------|
| **26-offline-evaluation** (AgentControl) | Name collides with SDK offline mode. The fixture / side-by-side prompt idea was declined. **Don't do.** |
| **Client offline mode** | Server fallbacks already live in [18-sdk-fallbacks](99-use-cases/18-sdk-fallbacks/). Client airplane-mode is a weak classroom demo. **Don't do.** It does not own a number. **37** is [37-client-evaluation-details](30-client-sdk/37-client-evaluation-details/). |
| **Online evals as their own series** | Dropped. **80** stays the next free decade. Judges already link the product docs from [24-agent-judges](20-agent-config/24-agent-judges/). |

Do not create a folder for offline evaluation, client offline mode, or an online-evals series.

## Notes

- 10-series **16** is percentage rollout, not migration flags. Migration remains [99-use-cases/17-migration-flags](99-use-cases/17-migration-flags/). **18** is approvals. **19** is evaluation reasons. Included-targets segments are the unnumbered [segment-targeting](10-code-control/segment-targeting/) folder. Letter suffixes (`1a`, `1b`) stay unused. If a decade has to grow, the refactor is three digits (`101`–`199`, `201`–`299`, `301`–`399`, …), done together. A fourth digit is not part of the scheme.
- 20-series **26** is [26-flags-vs-agent-control](20-agent-config/26-flags-vs-agent-control/). **27** is agent mode, **28** is context attributes, **29** is the team percentage rollout. [20-capstone](20-agent-config/20-capstone/) does not consume **27** and does not use the **29** lesson's ports. Capstone ports stay **:8290–:8293**. The image / essay / animal apps stay **70-model-demos**.
- **70-model-demos** children are `01`, `02`, `03`, `04` inside that folder. `04-terraform-codegen` is Python **:8740**. **80** stays the next free decade.
- Client bootstrap folder is `35-client-bootstrap`, not `bootstrapRender`.
- Track events: `login_completed` + `grid_move` only unless `cell_selected` is specified later.
