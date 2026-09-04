# lunch-marcoly

A collection of programming examples, each demonstrating a single concept across multiple languages. Examples are organized by topic — every example gets its own numbered directory, with language implementations nested inside.

## Structure

```
lunch-marcoly/
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
│   ├── portal/                   # Series shell: Python :8100
│   ├── 11-flag-enablement/       # Boolean flags + contexts
│   └── 12-flag-variations/       # String / number / JSON / anonymous
├── 20-agent-config/             # AgentControl series (shared setup)
│   ├── README.md
│   ├── portal/                   # Series shell: Python :8200 · Node :8201
│   ├── stories/                  # Shared Yahoo headlines cache
│   ├── 21-agent-completion-config/   # web + Go console
│   ├── 22-config-outside-code/       # web + Go console
│   ├── 23-agent-tools/               # web + Go console
│   └── 24-agent-judges/              # Judges gate (Python/Node/Java/.NET + Go console)
├── 30-client-sdk/               # Browser JavaScript SDK
│   ├── README.md
│   ├── portal/                  # Series shell: JS :8300 · React :8301 · Vue :8302
│   ├── 31-client-evaluation/    # initialize · variation · change: (:8310 JS · :8311 React · :8312 Vue)
│   ├── 32-client-identify/      # identify() without reload (:8320 JS · :8321 React · :8322 Vue)
│   ├── 33-synced-segments/      # synced/big segment badge (:8330 JS · :8331 React · :8332 Vue)
│   └── 34-synced-segments-twilio/  # Twilio Segment Audiences (:8340 JS · :8341 React · :8342 Vue)
├── 40-dont-do-this/             # Anti-patterns (do not ship)
│   ├── README.md
│   ├── 41-no-sdk-singleton/     # Stub: new LDClient per evaluation
│   └── 42-local-if-no-sdk/      # Stub: local if / no variation()
├── 50-mobile/                   # Mobile SDK series (2×2 tap navigator)
│   ├── README.md
│   ├── 51-reference/            # android/ · ios/ (no LaunchDarkly)
│   └── 52-mobile-evaluation/    # android/ · ios/ (mobile key)
├── 01-hello-world/
│   ├── README.md
│   ├── python/
│   └── rust/
└── ...
```

Examples are prefixed with a two-digit number (`00`, `01`, `02`, …) to control sort order.

## Languages

Each example may include implementations in any of these languages. Python, Node.js, Java, and **.NET** default to **web applications** with a browser UI. **JavaScript** (`javascript/`), **React Web** (`react/`), and **Vue** (`vue/`) are **browser applications**: the page owns the logic. **Android** (`android/`) and **iOS** (`ios/`) are **mobile applications** (2×2 tap navigator in series 50). Go, Rust, and C++ are **console applications**. Optional `-console` variants exist for Python, Node.js, and Java when a terminal-based version is also needed.

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
| 10 | [10-code-control](10-code-control/) | Feature-flag series (portal + examples 11–15) |
| 11 | [11-flag-enablement](10-code-control/11-flag-enablement/) | Grid navigator with LaunchDarkly boolean flags (all languages, Terraform + REST) |
| 12 | [12-flag-variations](10-code-control/12-flag-variations/) | Grid navigator with string, number, JSON, and anonymous flags (all languages) |
| 13 | [13-flag-targeting-rules](10-code-control/13-flag-targeting-rules/) | Targeting rules on a public `team` context attribute |
| 14 | [14-multi-context-targeting](10-code-control/14-multi-context-targeting/) | User + organization multi-context targeting |
| 15 | [15-prerequisite-flags](10-code-control/15-prerequisite-flags/) | Flag prerequisites: highlight must serve `green` before move count can evaluate |
| 20 | [20-agent-config](20-agent-config/) | AgentControl series (shared LLM / AWS / LD setup); [portal](20-agent-config/portal/) Python **:8200** · Node **:8201** |
| 21 | [21-agent-completion-config](20-agent-config/21-agent-completion-config/) | Completion config: model + system/user prompts (web + Go console) |
| 22 | [22-config-outside-code](20-agent-config/22-config-outside-code/) | Tracked completion: metrics + thumbs feedback (web + Go console) |
| 23 | [23-agent-tools](20-agent-config/23-agent-tools/) | Library tools + tool loop + `track_tool_call` (web + Go console) |
| 24 | [24-agent-judges](20-agent-config/24-agent-judges/) | Judges runtime gate + rewrite (Python **8240** · Node **8241** · Java **8242** · .NET **8243**; Go console) |
| 30 | [30-client-sdk](30-client-sdk/) | Browser client-side SDK series (client-side ID); [portal](30-client-sdk/portal/) JS **:8300** · React **:8301** · Vue **:8302** |
| 31 | [31-client-evaluation](30-client-sdk/31-client-evaluation/) | Initialize, client-side availability, `variation`, `change:` (**JS :8310** · **React :8311** · **Vue :8312**) |
| 32 | [32-client-identify](30-client-sdk/32-client-identify/) | `identify()` context switch without reload (**JS :8320** · **React :8321** · **Vue :8322**) |
| 33 | [33-synced-segments](30-client-sdk/33-synced-segments/) | Synced/big segment inner-circle badge (**JS :8330** · **React :8331** · **Vue :8332**) |
| 34 | [34-synced-segments-twilio](30-client-sdk/34-synced-segments-twilio/) | Twilio Segment Audiences sync (**JS :8340** · **React :8341** · **Vue :8342**) |
| 40 | [40-dont-do-this](40-dont-do-this/) | Anti-pattern series (do not ship); stub |
| 41 | [41-no-sdk-singleton](40-dont-do-this/41-no-sdk-singleton/) | Stub: new server SDK client per evaluation |
| 42 | [42-local-if-no-sdk](40-dont-do-this/42-local-if-no-sdk/) | Stub: local `if` / hardcoded boolean, never `variation()` |
| 50 | [50-mobile](50-mobile/) | Mobile SDK series (2×2 tap navigator; mobile key, not browser client-side ID) |
| 51 | [51-reference](50-mobile/51-reference/) | Mobile reference app — login, 2×2 tap grid, drawer; Android + iOS; no LaunchDarkly |
| 52 | [52-mobile-evaluation](50-mobile/52-mobile-evaluation/) | Mobile SDK: init, variation, listeners (`LD_MOBILE_KEY`; dedicated flag keys) |
| 99 | [99-use-cases](99-use-cases/) | Focused LaunchDarkly use cases (experiments, segments, rollouts, adaptive triggers, SDK fallbacks, …) |

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
