# lunch-marcoly

A collection of programming examples, each demonstrating a single concept across multiple languages. Examples are organized by topic — every example gets its own numbered directory, with language implementations nested inside.

## Structure

```
lunch-marcoly/
├── TODO.md                  # Next examples (see the queue)
├── requirements.txt         # Python dependencies (repository-wide)
├── .python-version          # Python version for pyenv (repository-wide)
├── .nvmrc                   # Node.js version for nvm (repository-wide)
├── .venv/                   # Python virtual environment (local)
├── .launchdarkly/           # LD inventory + visibility CLI (see README there)
├── 00-reference-code/
│   ├── README.md
│   ├── python/              # web application
│   ├── python-console/
│   ├── node/
│   ├── rust/                # console application
│   └── ...
├── 01-reference-agent/
│   ├── README.md
│   ├── application.md
│   ├── prompts/ · stories/  # shared system prompt + headline cache
│   ├── python/ · node/ · java/ · dotnet/         # web apps
│   ├── python-console/ · node-console/ · java-console/
│   └── go/ · rust/ · cpp/                        # console-only languages
├── 02-reference-client-code/
│   ├── README.md
│   ├── application.md
│   └── javascript/          # browser grid (static files, no LaunchDarkly)
├── 10-code-control/             # Feature-flag series
│   ├── README.md
│   ├── portal/                   # Python :8100 · Node :8101 · Java :8102 · .NET :8103
│   ├── 101-flag-enablement/
│   ├── 102-flag-variations/
│   ├── 103-flag-targeting-rules/
│   ├── 104-multi-context-targeting/
│   ├── 105-prerequisite-flags/
│   ├── 106-percentage-rollout/    # Web :8160–:8163 + consoles; static 30/70
│   ├── 107-scheduled-changes/     # Web :8170–:8173 + consoles; scheduled turn-on
│   ├── 108-flag-approvals/        # Stub: approval to enable move count
│   ├── 109-evaluation-reasons/    # Stub: four evaluation reason kinds
│   └── segment-targeting/        # Stub: included targets; still unnumbered
├── 20-agent-config/             # AgentControl series (shared setup)
│   ├── README.md
│   ├── portal/                   # Python :8200 · Node :8201 · Java :8202 · .NET :8203
│   ├── stories/                  # Shared Yahoo headlines cache
│   ├── 20-capstone-1/            # Python :8290 · Node :8291 · Java :8292 · .NET :8293; en/es; not in the portal
│   ├── 201-agent-completion-config/
│   ├── 202-config-outside-code/
│   ├── 203-agent-tools/
│   ├── 204-agent-judges/
│   ├── 205-agent-graph/          # assess → specialist → finalize
│   ├── 206-flags-vs-agent-control/ # Python :8260 · Node :8261 · Java :8262 · .NET :8263
│   ├── 207-agent-mode/           # Stub: agent mode only; not the capstone
│   ├── 208-context-attributes/   # Stub: region + audience select a variation
│   └── 209-team-rollout/         # Stub: sticky % rollout bucketed by team
├── 30-client-sdk/               # Browser JavaScript SDK
│   ├── README.md
│   ├── portal/                  # JS :8300 · React :8301 · Vue :8302 (301–306; portal paths still old)
│   ├── 301-client-evaluation/
│   ├── 302-client-identify/
│   ├── 303-synced-segments/
│   ├── 304-synced-segments-twilio/
│   ├── 305-client-bootstrap/    # Bootstrap first paint :8350–:8352
│   ├── 306-client-track-events/ # track() login_completed + grid_move :8360–:8362
│   ├── 307-client-evaluation-details/  # Stub: variationDetail vs variation
│   ├── 308-client-secure-mode/  # Stub: secure-mode hash
│   └── 309-client-context-cache/ # Stub: local storage cache, not bootstrap
├── 40-dont-do-this/             # Anti-patterns (do not ship)
│   ├── README.md
│   ├── 401-no-sdk-singleton/    # Stub: new LDClient per evaluation
│   └── 402-local-if-no-sdk/     # Stub: local if / no variation()
├── 50-mobile/                   # Mobile SDK series (2×2 tap navigator)
│   ├── README.md
│   ├── 51-reference/            # android/ · ios/ (no LaunchDarkly)
│   ├── 52-mobile-evaluation/    # android/ · ios/ (mobile key)
│   ├── 53-mobile-experiment/    # one experiment; platform is analysis dimension
│   ├── 54-platform-rollout/     # Android first, then iOS, one targeting rule
│   ├── 55-automatic-environment-attributes/  # Stub: SDK-supplied attributes
│   └── 56-mobile-multi-environment/          # Stub: two mobile keys
├── 60-observability/            # Server-side observability series
│   ├── 601-reference/            # Python-owned navigator API; no LaunchDarkly
│   ├── 602-server-traces/        # Python ObservabilityPlugin + manual move spans
│   ├── 603-server-errors/        # Stub: one error, also a log line; 604 stays free
│   └── 605-server-metrics/       # Stub: one custom metric
├── 70-model-demos/              # Model apps; children 01–04 inside the folder
│   ├── README.md                # 80 remains the next free decade
│   ├── 01-image-processing/     # Stub: four cat photos
│   ├── 02-text-origin/          # Stub: human vs AI essay
│   ├── 03-guess-the-animal/     # Stub: yes/no until the model names it
│   └── 04-terraform-codegen/    # Two models, one Terraform file; Python :8740
├── 99-use-cases/                # Product patterns on the grid navigator
│   ├── 01-abcd-test/
│   ├── 02-segments-by-name/
│   ├── 11-create-eval-flag/
│   ├── 14-progressive-rollout/
│   ├── 15-guarded-rollout/
│   ├── 16-adaptive-triggers/
│   ├── 17-migration-flags/      # Stub
│   ├── 18-sdk-fallbacks/
│   ├── 19-terraform-sentinel/   # Sentinel policies for Terraform flags
│   ├── 20-multi-arm-bandit/     # Stub: bandit shifts traffic; grid, not mobile
│   └── 21-tenant-datacenters/   # Five datacenters, 52 tenants, palette and fill flags
├── 01-hello-world/
│   ├── README.md
│   ├── python/
│   └── rust/
└── ...
```

Examples are prefixed with a two-digit number (`00`, `01`, `02`, …) to control sort order. **10-code-control** children are **101–109**, **20-agent-config** children are **201–209** (capstone folder `20-capstone-1`), and **30-client-sdk** children are **301–309**. **40-dont-do-this** children are **401** and **402**. **60-observability** children are **601**, **602**, **603**, and **605**. **604** stays free. Other decade series still use two-digit children (`51`–`56`, …) until that series is renumbered. Letter suffixes stay unused. A fourth digit is not part of the scheme.

## Languages

Each example may include implementations in any of these languages. Every application includes an **About** page: on a web example it is a tab in the drawer that shows the application-related details; a console example puts that same explanation in its README. Python, Node.js, Java, and **.NET** default to **web applications** with a browser UI. **JavaScript** (`javascript/`), **React Web** (`react/`), and **Vue** (`vue/`) are **browser applications**: the page owns the logic. **Android** (`android/`) and **iOS** (`ios/`) are **mobile applications** (2×2 tap navigator in series 50). Go, Rust, and C++ are **console applications**. Optional `-console` variants exist for Python, Node.js, and Java when a terminal-based version is also needed.

| Language | Directory | Application type |
|----------|-----------|------------------|
| Python   | `python/` | Web application |
| Python   | `python-console/` | Console application |
| Node.js  | `node/`   | Web application |
| Node.js  | `node-console/` | Console application |
| Java     | `java/`   | Web application |
| Java     | `java-console/` | Console application |
| .NET     | `dotnet/` | Web application |
| C++      | `cpp/`    | Console application |
| Go       | `go/`     | Console application |
| Rust     | `rust/`   | Console application |
| JavaScript | `javascript/` | Browser application (static files) |
| React Web | `react/` | Browser application (Vite + React Web SDK) |
| Vue       | `vue/` | Browser application (Vite + Vue SDK) |
| Android  | `android/` | Mobile application (Kotlin / Compose) |
| iOS      | `ios/` | Mobile application (Swift / SwiftUI) |
| React Native | `react-native/` | Mobile application (later; series 50) |

## Examples

| # | Directory | Description |
|---|-----------|-------------|
| 00 | [00-reference-code](00-reference-code/) | Grid navigator reference app (all languages, no LaunchDarkly) |
| 01 | [01-reference-agent](01-reference-agent/) | News headlines → AI equity briefing (Python / Node / Java / .NET web + consoles; LaunchDarkly comes in later examples) |
| 02 | [02-reference-client-code](02-reference-client-code/) | Browser grid navigator (JavaScript in the page, no LaunchDarkly) |
| 10 | [10-code-control](10-code-control/) | Feature-flag series (101–107 built; 108, 109, and segment-targeting are stubs) |
| 101 | [101-flag-enablement](10-code-control/101-flag-enablement/) | Grid navigator with LaunchDarkly boolean flags (all languages, Terraform + REST) |
| 102 | [102-flag-variations](10-code-control/102-flag-variations/) | Grid navigator with string, number, JSON, and anonymous flags (all languages) |
| 103 | [103-flag-targeting-rules](10-code-control/103-flag-targeting-rules/) | Targeting rules on a public `team` context attribute |
| 104 | [104-multi-context-targeting](10-code-control/104-multi-context-targeting/) | User + organization multi-context targeting |
| 105 | [105-prerequisite-flags](10-code-control/105-prerequisite-flags/) | Flag prerequisites: highlight must serve `green` before move count can evaluate |
| 106 | [106-percentage-rollout](10-code-control/106-percentage-rollout/) | Static 30/70 percentage rollout, sticky context key (web **:8160–:8163** + Python / Node / Java / Go / Rust / C++ consoles) |
| 107 | [107-scheduled-changes](10-code-control/107-scheduled-changes/) | Replaceable scheduled flag turn-on with elapsed timer (web **:8170–:8173** + Python / Node / Java / Go / Rust / C++ consoles + REST/Terraform) |
| 108 | [108-flag-approvals](10-code-control/108-flag-approvals/) | **Stub:** approval to turn the move-count flag on |
| 109 | [109-evaluation-reasons](10-code-control/109-evaluation-reasons/) | **Stub:** on-screen `PREREQUISITE_FAILED`, `RULE_MATCH`, `FALLTHROUGH`, `ERROR` |
| — | [segment-targeting](10-code-control/segment-targeting/) | **Stub:** included-targets segment. Unnumbered so it does not take 20. Read before 303 |
| 20 | [20-agent-config](20-agent-config/) | AgentControl series (shared LLM / AWS / LD setup); [portal](20-agent-config/portal/) Python **:8200** · Node **:8201** · Java **:8202** · .NET **:8203** |
| — | [20-capstone-1](20-agent-config/20-capstone-1/) | **Python :8290 · Node :8291 · Java :8292 · .NET :8293, not in the portal.** Composes `201`–`205`. Checked tools run before finalize. Judges and feedback stay on the draft. English and Spanish live here |
| 201 | [201-agent-completion-config](20-agent-config/201-agent-completion-config/) | Completion config: model + system/user prompts (web + Go console) |
| 202 | [202-config-outside-code](20-agent-config/202-config-outside-code/) | Tracked completion: metrics + thumbs feedback (web + Go console) |
| 203 | [203-agent-tools](20-agent-config/203-agent-tools/) | Library tools + tool loop + `track_tool_call` (web + Go console) |
| 204 | [204-agent-judges](20-agent-config/204-agent-judges/) | Judges runtime gate + rewrite (Python **8240** · Node **8241** · Java **8242** · .NET **8243**; Go console) |
| 205 | [205-agent-graph](20-agent-config/205-agent-graph/) | Agent graph: assess → specialist → finalize (Python **8250** · Node **8251** · Java **8252** · .NET **8253**) |
| 206 | [206-flags-vs-agent-control](20-agent-config/206-flags-vs-agent-control/) | Python **:8260**, Node **:8261**, Java **:8262**, .NET **:8263**. AgentControl, four flags, or one JSON flag. Guardrail scores pass/fail |
| 207 | [207-agent-mode](20-agent-config/207-agent-mode/) | **Stub:** agent mode only, one instructions value. Does not roll into the capstone |
| 208 | [208-context-attributes](20-agent-config/208-context-attributes/) | **Stub:** North America / South America and an audience select the variation |
| 209 | [209-team-rollout](20-agent-config/209-team-rollout/) | **Stub:** sticky percentage rollout bucketed by `team`. Not ports :8290–:8293 |
| 30 | [30-client-sdk](30-client-sdk/) | Browser client-side SDK series (client-side ID); [portal](30-client-sdk/portal/) JS **:8300** · React **:8301** · Vue **:8302** (301–306; portal paths still old) |
| 301 | [301-client-evaluation](30-client-sdk/301-client-evaluation/) | Initialize, client-side availability, `variation`, `change:` (**JS :8310** · **React :8311** · **Vue :8312**) |
| 302 | [302-client-identify](30-client-sdk/302-client-identify/) | `identify()` context switch without reload (**JS :8320** · **React :8321** · **Vue :8322**) |
| 303 | [303-synced-segments](30-client-sdk/303-synced-segments/) | Synced/big segment inner-circle badge (**JS :8330** · **React :8331** · **Vue :8332**) |
| 304 | [304-synced-segments-twilio](30-client-sdk/304-synced-segments-twilio/) | Twilio Segment Audiences sync (**JS :8340** · **React :8341** · **Vue :8342**) |
| 305 | [305-client-bootstrap](30-client-sdk/305-client-bootstrap/) | Bootstrap first paint (`green` / count on) before the client is ready |
| 306 | [306-client-track-events](30-client-sdk/306-client-track-events/) | Client `track()` — `login_completed`, `grid_move` (**JS :8360** · **React :8361** · **Vue :8362**) |
| 307 | [307-client-evaluation-details](30-client-sdk/307-client-evaluation-details/) | **Stub:** `variationDetail()` next to `variation()` |
| 308 | [308-client-secure-mode](30-client-sdk/308-client-secure-mode/) | **Stub:** secure-mode hash for the browser context |
| 309 | [309-client-context-cache](30-client-sdk/309-client-context-cache/) | **Stub:** local storage cache, called out in the UI. Not 305 |
| 40 | [40-dont-do-this](40-dont-do-this/) | Anti-pattern series (do not ship) |
| 401 | [401-no-sdk-singleton](40-dont-do-this/401-no-sdk-singleton/) | **Stub:** new server SDK client per evaluation |
| 402 | [402-local-if-no-sdk](40-dont-do-this/402-local-if-no-sdk/) | **Stub:** local `if` / hardcoded boolean, never `variation()` |
| 50 | [50-mobile](50-mobile/) | Mobile SDK series (2×2 tap navigator; mobile key, not browser client-side ID) |
| 51 | [51-reference](50-mobile/51-reference/) | Mobile reference app — login, 2×2 tap grid, drawer; Android + iOS; no LaunchDarkly |
| 52 | [52-mobile-evaluation](50-mobile/52-mobile-evaluation/) | Mobile SDK: init, variation, listeners (`LD_MOBILE_KEY`; dedicated flag keys) |
| 53 | [53-mobile-experiment](50-mobile/53-mobile-experiment/) | Android+iOS Experimentation: one flag, exposure→conversion, results by platform, synthetic traffic |
| 54 | [54-platform-rollout](50-mobile/54-platform-rollout/) | Staggered release by platform: Android first, then add iOS to the same rule |
| 55 | [55-automatic-environment-attributes](50-mobile/55-automatic-environment-attributes/) | **Stub:** automatic environment attributes on Android and iOS |
| 56 | [56-mobile-multi-environment](50-mobile/56-mobile-multi-environment/) | **Stub:** two environments, two mobile keys |
| 60 | [60-observability](60-observability/) | Observability series: Python server-side telemetry on the grid navigator |
| 601 | [601-reference](60-observability/601-reference/) | Server-owned Python navigator baseline (**:8610**; no LaunchDarkly) |
| 602 | [602-server-traces](60-observability/602-server-traces/) | Python `ObservabilityPlugin` + `grid.login` / `grid.move` spans (**:8620**) |
| 603 | [603-server-errors](60-observability/603-server-errors/) | **Stub:** one deliberate error, visible as an error and a log line. **604** stays free |
| 605 | [605-server-metrics](60-observability/605-server-metrics/) | **Stub:** one custom metric. 602 stays spans |
| 70 | [70-model-demos](70-model-demos/) | Model apps. Children `01`–`04` inside the folder. `01`–`03` are stubs. `04-terraform-codegen` is Python **:8740**. **80** stays free |
| 99 | [99-use-cases](99-use-cases/) | Focused LaunchDarkly use cases (experiments, segments, rollouts, adaptive triggers, SDK fallbacks, …) |
| — | [01-abcd-test](99-use-cases/01-abcd-test/) | A-B-C-D experiment on the navigation count label |
| — | [02-segments-by-name](99-use-cases/02-segments-by-name/) | Segment targeting from username-derived context |
| — | [11-create-eval-flag](99-use-cases/11-create-eval-flag/) | Create and evaluate a single highlight flag |
| — | [14-progressive-rollout](99-use-cases/14-progressive-rollout/) | Time-staged 10→100% highlight ramp (not 16’s static %) |
| — | [15-guarded-rollout](99-use-cases/15-guarded-rollout/) | Percentage ramp with regression guardrails |
| — | [16-adaptive-triggers](99-use-cases/16-adaptive-triggers/) | Metric threshold switches flag variation |
| — | [17-migration-flags](99-use-cases/17-migration-flags/) | **Stub:** migration flag dual-store cutover |
| — | [18-sdk-fallbacks](99-use-cases/18-sdk-fallbacks/) | Init failure / stream loss → default vs last-known |
| — | [19-terraform-sentinel](99-use-cases/19-terraform-sentinel/) | Sentinel pass/fail fixtures: temporary flags and a sunset custom property |
| — | [20-multi-arm-bandit](99-use-cases/20-multi-arm-bandit/) | **Stub:** multi-armed bandit on the grid navigator. Allocation moves with a metric |
| — | [21-tenant-datacenters](99-use-cases/21-tenant-datacenters/) | Five datacenters, 52 tenants. Border palette, fill, and segments |

## Building code

Each implementation **builds locally** in its language folder. Runnable artifacts are named after the **example directory** (e.g. `00-reference-code.py`, `./00-reference-code`, `target/00-reference-code.jar`).

Full conventions are in [project.md](project.md#building-and-running). Summary:

### Python and pyenv

This project requires **Python 3.12 or higher**. Use [pyenv](https://github.com/pyenv/pyenv) to install and select the correct version — especially if your system `python3` is older.

A [`.python-version`](.python-version) file at the repository root tells pyenv which version to use:

```bash
pyenv install 3.12          # once, if not already installed
cd lunch-marcoly            # pyenv reads .python-version automatically
python --version            # should report 3.12.x
```

If pyenv is not active in your shell, add its init hook to your profile (see the [pyenv installation docs](https://github.com/pyenv/pyenv#installation)).

Then create the shared virtual environment at the repository root:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Activate `.venv` whenever you work on Python examples. Use `python` (not an older system `python3`) inside the venv.

### One-time setup (other toolchains)

**Node.js** — use [nvm](https://github.com/nvm-sh/nvm) to install and select the Node version for this repository. An `.nvmrc` at the repository root pins the expected major version:

```bash
nvm install          # reads .nvmrc (Node 20 LTS)
nvm use              # activate that version in the current shell
node -v              # should report v20.x
```

Run `nvm use` whenever you open a new shell before working on Node examples.

**Other toolchains** — install only what you need:

| Language | Install |
|----------|---------|
| Python   | [pyenv](https://github.com/pyenv/pyenv) — see [Python and pyenv](#python-and-pyenv) |
| Node.js  | [nvm](https://github.com/nvm-sh/nvm) — see above |
| Java     | [adoptium.net](https://adoptium.net/) 21+ (Maven Wrapper included per project) |
| .NET     | [dotnet.microsoft.com](https://dotnet.microsoft.com/download) SDK **10+** (often `/usr/local/share/dotnet` on macOS) |
| C++      | C++20 compiler and Make |
| Go       | [go.dev](https://go.dev/dl/) **1.22+** (AgentControl `go/` modules may require **1.24** — see each `go.mod`) |
| Rust     | [rustup.rs](https://rustup.rs/) 1.75+ |
| Android  | [Android Studio](https://developer.android.com/studio) (JDK 17+, SDK; Gradle Wrapper in each `android/`) |
| iOS      | [Xcode](https://developer.apple.com/xcode/) 15+ (macOS) |

### Build patterns (from each language folder)

| Language | Build | Run (artifact name varies by example) |
|----------|-------|---------------------------------------|
| Python | *(no compile step)* | `python 00-reference-code.py` |
| Node.js | `npm install` *(when deps exist)* | `node 00-reference-code.js` |
| JavaScript | `npm install` *(when deps exist)* | `npm start` (static server) |
| React Web | `npm install` | `npm start` (Vite; 31 is **:8311**) |
| Vue | `npm install` | `npm start` (Vite; 31 is **:8312**) |
| Java | `./mvnw clean install` | `java -jar target/00-reference-code.jar` |
| .NET | `export PATH="/usr/local/share/dotnet:$PATH"` · `dotnet restore` · `dotnet build` | `dotnet run` (TFM **net10.0**) |
| C++ | `make clean && make all` | `./00-reference-code` |
| Go | `go mod tidy` · `go build -o <example-name> .` | `./<example-name>` |
| Rust | `cargo build --release` | `./target/release/00-reference-code` |
| Android | `./gradlew assembleDebug` | Android Studio → Run, or install the debug APK |
| iOS | Open `*.xcodeproj` | Xcode → Run on Simulator |

Each language folder's `README.md` lists the exact **Build** and **Run** commands for that implementation.

## Quick Start

1. Clone the repository.
2. Set up Python with [pyenv](#python-and-pyenv) and other toolchains as needed (see [Building code](#building-code)).
3. Open an example (e.g. [00-reference-code](00-reference-code/)).
4. Open a language subdirectory and follow its `README.md`.

## Project Conventions

See [project.md](project.md) for the full specification covering:

- Repository layout and folder structure
- Build and run conventions
- Web vs console application types
- Numbering and naming conventions
- Required README format
- LaunchDarkly requirements and provisioning

## Adding an Example

```bash
# 1. Pick the next number and create the directory
mkdir -p 01-hello-world/python 01-hello-world/rust

# 2. Add a top-level README.md describing the concept
# 3. Add code and a README.md inside each language folder
# 4. Verify each implementation builds and runs from a clean environment
```
