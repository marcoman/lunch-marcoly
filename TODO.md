# TODO

Work queue for new lunch-marcoly examples. Ship in this order.

## Next

30-client-sdk folders are **301–309**. JavaScript, React, and Vue in **301–306** use the new numbers, including an About tab. The portal still uses the old names. Remaining stubs:

- [401-no-sdk-singleton](40-dont-do-this/401-no-sdk-singleton/)
- [402-local-if-no-sdk](40-dont-do-this/402-local-if-no-sdk/)
- [99-use-cases/17-migration-flags](99-use-cases/17-migration-flags/)
- [99-use-cases/20-multi-arm-bandit](99-use-cases/20-multi-arm-bandit/) — grid bandit; not `503-mobile-experiment`
- [20-agent-management/20-capstone-1](20-agent-management/20-capstone-1/) — outside **201–209**. Python **:8290**, Node **:8291**, Java **:8292**, .NET **:8293** built, not in the portal. Graph is assess → specialist → finalize. Checked tools (Pig Latin, ROT13, joke tagline) run after the draft and before finalize. Judges and feedback stay on the draft. `201`–`205` stay as they are. English and Spanish live here. Later lessons keep their own numbers and do not roll into the capstone.

New stubs (README only, not built):

- [108-flag-approvals](10-feature-management/108-flag-approvals/) — approval to turn the move-count flag on. Ports **:8180–:8183** when built.
- [109-evaluation-reasons](10-feature-management/109-evaluation-reasons/) — `PREREQUISITE_FAILED`, `RULE_MATCH`, `FALLTHROUGH`, `ERROR` on screen. Ports **:8190–:8193** when built.
- [segment-targeting](10-feature-management/segment-targeting/) — included-targets segment, server SDK. Still unnumbered. Read this before [303-synced-segments](30-client-sdk/303-synced-segments/).
- [207-agent-mode](20-agent-management/207-agent-mode/) — agent mode only, one instructions value. Does not roll into the capstone. Ports **:8270–:8273**.
- [208-context-attributes](20-agent-management/208-context-attributes/) — region and audience select a variation. Not `{{ }}` prompt variables. Ports **:8280–:8283**.
- [209-team-rollout](20-agent-management/209-team-rollout/) — sticky percentage rollout bucketed by `team`. Not [14-progressive-rollout](99-use-cases/14-progressive-rollout/). Do not use ports **:8290–:8293** (capstone).
- [307-client-evaluation-details](30-client-sdk/307-client-evaluation-details/) — client `variationDetail()` next to `variation()`.
- [308-client-secure-mode](30-client-sdk/308-client-secure-mode/)
- [309-client-context-cache](30-client-sdk/309-client-context-cache/) — local storage cache, called out in the UI. Not [305-client-bootstrap](30-client-sdk/305-client-bootstrap/).
- [505-automatic-environment-attributes](50-mobile/505-automatic-environment-attributes/)
- [506-mobile-multi-environment](50-mobile/506-mobile-multi-environment/)
- [603-server-errors](60-observability/603-server-errors/) — one deliberate error, visible as an error and a log line. **604** stays free.
- [605-server-metrics](60-observability/605-server-metrics/) — custom metric. [602-server-traces](60-observability/602-server-traces/) is spans only.
- [701-image-processing](70-model-demos/701-image-processing/), [702-text-origin](70-model-demos/702-text-origin/), [703-guess-the-animal](70-model-demos/703-guess-the-animal/) — plan these next to [704-terraform-codegen](70-model-demos/704-terraform-codegen/). Not a new decade.
- [25-prerequisite-tree](99-use-cases/25-prerequisite-tree/) — six flags: one grandparent, two parents, three children. The drawer tree is the lesson. Extends [105-prerequisite-flags](10-feature-management/105-prerequisite-flags/).
- [26-agent-adaptive-trigger](99-use-cases/26-agent-adaptive-trigger/) — Agent Management stand-in for [16-adaptive-triggers](99-use-cases/16-adaptive-triggers/). A metric switches the briefing to a safer model. Placeholder only.
- [27-archive-flag](99-use-cases/27-archive-flag/) — selected cell blinks while the flag is on, then stops when the flag is archived. The page steps through setup, run, and archive. Not a 10-series number.
- [playgrounds](20-agent-management/playgrounds/) — unnumbered. Sandbox Toby against Charlie on the existing stock-picker configs. Not a 70 app, and not **210**.
- [28-big-segment](99-use-cases/28-big-segment/) — server-side big segment backed by one DynamoDB table in us-east-1. Not [303-synced-segments](30-client-sdk/303-synced-segments/).
- [705-offline-evaluations](70-model-demos/705-offline-evaluations/) — dataset of Terraform briefs, two models, pass or fail per row. Not the 204 runtime judges.

## Don't do

| Idea | Why not |
|------|---------|
| **26-offline-evaluation** (Agent Management) | Name collides with SDK offline mode. The fixture / side-by-side prompt idea was declined. **Don't do.** |
| **Client offline mode** | Server fallbacks already live in [18-sdk-fallbacks](99-use-cases/18-sdk-fallbacks/). Client airplane-mode is a weak classroom demo. **Don't do.** It does not own a number. **307** is [307-client-evaluation-details](30-client-sdk/307-client-evaluation-details/). |
| **Online evals as their own series** | Dropped. **80** stays the next free decade. Judges already link the product docs from [204-agent-judges](20-agent-management/204-agent-judges/). |

Do not create a folder for offline evaluation, client offline mode, or an online-evals series.

## Notes

- 10-series children are **101–109**. **106** is percentage rollout, not migration flags. Migration remains [99-use-cases/17-migration-flags](99-use-cases/17-migration-flags/). **108** is approvals. **109** is evaluation reasons. Included-targets segments are the unnumbered [segment-targeting](10-feature-management/segment-targeting/) folder. Web and console entrypoints for 101–107 use those numbers. Ports for 101–107 stay **8110–8170**. Letter suffixes stay unused. **20-agent-management** children are **201–209**, and the capstone is [20-capstone-1](20-agent-management/20-capstone-1/). **30-client-sdk** children are **301–309**. JavaScript, React, and Vue in **301–306** use those numbers, including an About tab. Stub READMEs use **307–309**. The portal still uses the old names. Ports stay **8310–8362**. **40-dont-do-this** children are **401** and **402**. **60-observability** children are **601**, **602**, **603**, and **605**. **604** stays free. Ports stay **8610**, **8620**, **8630**, and **8650**. Other series stay two-digit until their own renumber (`501`–`599`, …). A fourth digit is not part of the scheme.
- 20-series **206** is [206-flags-vs-agent-management](20-agent-management/206-flags-vs-agent-management/). **207** is agent mode, **208** is context attributes, **209** is the team percentage rollout. [20-capstone-1](20-agent-management/20-capstone-1/) does not consume **207** and does not use the **209** lesson's ports. Capstone ports stay **:8290–:8293**. Web entrypoints for 201–206 and 20-capstone-1 use the new numbers in Python, Node, Java, and .NET. Portals use tab ids 201–206. Console entrypoints in this series still use the old names. The image / essay / animal apps stay **70-model-demos**.
- **70-model-demos** children are `701`–`704` inside that folder (`701`–`703` are stubs). `704-terraform-codegen` is Python **:8740**. **80** stays the next free decade.
- Client bootstrap folder is `305-client-bootstrap`, not `bootstrapRender`.
- Track events: `login_completed` + `grid_move` only unless `cell_selected` is specified later.
