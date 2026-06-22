# Project Specification

This document defines the structure, conventions, and standards for **lunch-marcoly** — a collection of small, self-contained programming examples, each implemented across multiple languages.

For the reference grid navigator application behavior, see [00-reference/application.md](00-reference/application.md).

## Purpose

Each example demonstrates a specific concept, pattern, or technique using [LaunchDarkly](https://launchdarkly.com/docs/home). The same idea is implemented in several languages so they can be compared side by side. Examples are independent: they should run on their own without depending on other examples in the repository.

Not every example needs implementations in all languages — add language folders only where an implementation exists.

Supported languages and application types:

| Language | Directory | Application type | Package manager / build tool |
|----------|-----------|------------------|------------------------------|
| Python   | `python/` | Web application  | pyenv + pip (root `.venv`)   |
| Python   | `python-console/` | Console application | pyenv + pip (root `.venv`) |
| Node.js  | `node/`   | Web application  | nvm + npm                    |
| Node.js  | `node-console/` | Console application | nvm + npm              |
| Java     | `java/`   | Web application  | Maven (wrapper)              |
| Java     | `java-console/` | Console application | Maven (wrapper)         |
| C++      | `cpp/`    | Console application | Make                         |
| Go       | `go/`     | Console application | go modules                   |
| Rust     | `rust/`   | Console application | Cargo                     |

**Web applications** (`python/`, `node/`, `java/`) include a graphical component served in the browser. Each README should document how to start the local server and which URL to open.

**Console applications** (`python-console/`, `node-console/`, `java-console/`, `cpp/`, `rust/`) run in the terminal with text-based input and output.

Use the default language directory when adding a web implementation. Add the `-console` variant only when an example also needs a terminal-based version of the same concept in that language.

## Repository Layout

Examples are the primary organizational unit. Language folders live inside each example.

```
lunch-marcoly/
├── README.md
├── project.md
├── requirements.txt           # Python dependencies (repository-wide)
├── .python-version            # Python version for pyenv (repository-wide)
├── .nvmrc                     # Node.js version for nvm (repository-wide)
├── .venv/                     # Python virtual environment (local, not committed)
├── 00-reference/              # Reference grid navigator — no LaunchDarkly
│   ├── README.md
│   ├── application.md         # Grid navigator behavior spec (00-reference only)
│   ├── python/
│   ├── python-console/
│   ├── node/
│   ├── node-console/
│   ├── java/
│   ├── java-console/
│   ├── cpp/                   # Makefile → ./00-reference
│   ├── go/
│   └── rust/
├── 10-flag-enablement/        # Feature flags for the grid navigator
│   ├── README.md
│   ├── application.md         # Flag specification and desired effects
│   ├── rest/                  # REST API provisioning
│   ├── terraform/             # Terraform provisioning
│   └── <language[-console]>/  # Future: flag evaluation implementations
├── 11-flag-variations/        # String, number, JSON, and anonymous flag types
│   ├── README.md
│   ├── application.md
│   ├── rest/
│   ├── terraform/
│   └── <language[-console]>/
├── 99-use-cases/              # Focused LaunchDarkly use-case examples
│   ├── README.md
│   └── 01-abcd-test/          # A-B-C-D test on navigation count label
├── 01-hello-world/
│   ├── README.md
│   ├── rest/
│   ├── terraform/
│   ├── python/
│   ├── python-console/
│   └── rust/
└── <NN-example-name>/
    ├── README.md
    ├── rest/
    ├── terraform/
    └── <language[-console]>/
```

## Naming Conventions

### Example directories (top level)

- Prefix with a **two-digit number**: `00-reference`, `01-hello-world`, `02-binary-search`
- Follow the number with a **kebab-case** name describing the concept
- Use the next available number when adding a new example (`03`, `04`, …)
- `00-reference` is reserved for the reference grid navigator app and repository conventions. It does **not** include LaunchDarkly integration.
- `10-flag-enablement` demonstrates feature flag naming, provisioning, and enablement for the grid navigator.
- `11-flag-variations` demonstrates string, number, JSON, and anonymous-context flag variation types.
- `99-use-cases` holds focused LaunchDarkly patterns built on the reference app (e.g. A-B-C-D tests).
- Be descriptive and concise: prefer `rate-limiter` over `rl`
- Name after the concept being demonstrated, not a language or author

### Language directories (inside an example)

- Use the fixed directory names from the table above
- Web implementations: `python/`, `node/`, `java/`
- Console implementations: `python-console/`, `node-console/`, `java-console/`, `cpp/`, `rust/`
- Only create a language folder when that implementation exists
- Do not nest `-console` folders inside their web counterparts — each is a sibling directory at the example root

### Source files

Follow the idiomatic naming style of each language:

| Language | Directory | File naming              | Example              |
|----------|-----------|--------------------------|----------------------|
| Python   | `python/`, `python-console/` | `{example-name}.py` | `00-reference.py` |
| Node.js  | `node/`, `node-console/` | `{example-name}.js` | `00-reference.js` |
| Java     | `java/`, `java-console/` | PascalCase (classes) | `WebServer.java` |
| C++      | `cpp/`    | `main.cpp` + Makefile | binary `00-reference` |
| Go       | `go/`     | `main.go` | binary `00-reference` |
| Rust     | `rust/`   | `src/main.rs` | binary `00-reference` |

The **runnable artifact name** matches the **example directory name** (e.g. `00-reference`, `01-hello-world`). Language READMEs document the exact build and run commands for that folder.

### README files

Every example directory **must** include a top-level `README.md` with:

1. **What this demonstrates** — the concept in one or two paragraphs
2. **Prerequisites** — LaunchDarkly account, provisioning steps, shared env vars
3. **Language implementations** — table linking to each language directory with application type and status
4. **Further reading** — links to LaunchDarkly docs and related examples

Each language subdirectory **must** include its own `README.md` with:

1. **Prerequisites** — language version, tools, dependencies (see [Requirements](#language-and-tooling))
2. **Environment variables** — which `LD_*` variables the implementation needs
3. **Build** — exact commands to compile or prepare the application in that folder (see [Building and running](#building-and-running))
4. **Run** — exact command to start the application, citing the executable or script name (e.g. `./00-reference`, `python3 00-reference.py`)
5. **What to expect** — output or behavior description (terminal output for console apps; UI behavior and URL for web apps)

Each `rest/` and `terraform/` folder **must** include a `README.md` with:

1. **Prerequisites** — tools (`curl`, Terraform, etc.)
2. **Environment variables** — required `LD_*` variables for that approach
3. **How to run** — exact commands to create or update LaunchDarkly resources
4. **What to expect** — resources created and how to verify them

## Example Structure

A minimal example with one web implementation:

```
01-hello-world/
├── README.md                 # Concept overview
├── rest/                     # Provisioning via REST API
│   └── README.md
├── terraform/                # Provisioning via Terraform
│   └── README.md
└── python/                   # Web application
    ├── README.md
    └── 00-reference.py
```

A fuller example with web, console, and native implementations:

```
01-hello-world/
├── README.md
├── rest/
│   └── README.md
├── terraform/
│   ├── README.md
│   └── main.tf
├── python/                   # Web application
│   ├── README.md
│   └── 00-reference.py
├── python-console/           # Console alternative
│   ├── README.md
│   └── 00-reference.py
├── node/
│   ├── README.md
│   ├── package.json
│   └── 00-reference.js
└── rust/                     # Console application
    ├── README.md
    ├── Cargo.toml
    └── src/main.rs
```

Larger examples may add tests, config files, or sub-packages as appropriate for the language, but keep the scope small and focused.

### Dependency files

Repository-wide and per-language dependency conventions:

| Scope | File | Purpose |
|-------|------|---------|
| Repository root | `requirements.txt` | **All** Python dependencies for every example |
| Repository root | `.python-version` | Python version pin for [pyenv](https://github.com/pyenv/pyenv) (3.12+) |
| Repository root | `.venv/` | Shared Python virtual environment (create locally; not committed) |
| Repository root | `.nvmrc` | Node.js version pin for [nvm](https://github.com/nvm-sh/nvm) |
| Node.js | `node/`, `node-console/` → `package.json` | Per-folder Node metadata and scripts |
| Java | `java/`, `java-console/` → `pom.xml` | Maven build; use `./mvnw` (Maven Wrapper) |
| Java | `mvnw`, `.mvn/wrapper/` | Maven Wrapper — preferred over a system `mvn` install |
| C++ | `cpp/` → `Makefile` | Must provide `all` and `clean` targets |
| Go | `go/` → `go.mod` | Go modules |
| Rust | `rust/` → `Cargo.toml` | Cargo; binary name matches example directory |

Do not commit lock files (`package-lock.json`, `Cargo.lock`, etc.) unless an implementation specifically requires reproducible builds.

## Building and running

Every implementation **builds locally** inside its language folder. The root [README.md](README.md) describes one-time setup; each language README lists the exact **build** and **run** commands for that folder.

### Artifact naming

The runnable artifact uses the **example directory name**:

| Example folder | Python script | Node script | C++ / Go binary | Rust binary | Java JAR |
|----------------|---------------|-------------|-----------------|-------------|----------|
| `00-reference` | `00-reference.py` | `00-reference.js` | `./00-reference` | `./target/release/00-reference` | `target/00-reference.jar` |
| `01-hello-world` | `01-hello-world.py` | `01-hello-world.js` | `./01-hello-world` | `./target/release/01-hello-world` | `target/01-hello-world.jar` |

### Python

- **Version:** Python **3.12+** required. Use [pyenv](https://github.com/pyenv/pyenv) when the system interpreter is older.
- **Version pin:** [`.python-version`](.python-version) at the repository root (read by pyenv).
- **Dependencies:** single [requirements.txt](requirements.txt) at the repository root.
- **Virtual environment:** one shared `.venv/` at the repository root.

```bash
# Once, from the repository root
pyenv install 3.12              # if needed
python --version                # expect 3.12.x
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

- **Build:** no separate compile step (interpreted).
- **Run:** from the language folder, with pyenv and the virtual environment active:

```bash
python 00-reference.py
```

Language READMEs cite the exact script name.

### Node.js

- **Version management:** use [nvm](https://github.com/nvm-sh/nvm). The repository root [`.nvmrc`](.nvmrc) pins the Node major version (20 LTS). From the repository root:

```bash
nvm install
nvm use
```

Run `nvm use` in each new shell before building or running Node examples.

- **Dependencies:** `package.json` in each `node/` or `node-console/` folder.
- **Build:** install dependencies when the folder declares them:

```bash
npm install
```

- **Run:**

```bash
node 00-reference.js
# or
npm start
```

### Java

- **Build tool:** Maven only. Every Java folder includes the **Maven Wrapper** (`./mvnw`).
- **Build:** from the Java language folder:

```bash
./mvnw clean install
```

- **Run:** JAR name matches the example directory:

```bash
java -jar target/00-reference.jar
```

Prefer `./mvnw` over a system-wide `mvn` install for consistency.

### C++

- **Build:** every `cpp/` folder includes a **Makefile** with `all` and `clean` targets:

```bash
make clean
make all
```

- **Run:** binary name matches the example directory:

```bash
./00-reference
```

### Go

- **Build:** from the `go/` folder:

```bash
go build -o 00-reference .
```

- **Run:**

```bash
./00-reference
```

### Rust

- **Build:** from the `rust/` folder:

```bash
cargo build --release
```

- **Run:**

```bash
./target/release/00-reference
```

The Cargo `[bin]` name matches the example directory.

### Documentation split

| Document | Build/run content |
|----------|-------------------|
| [README.md](README.md) | One-time setup (venv, toolchains), general expectations |
| [project.md](project.md) | Canonical build conventions (this section) |
| Example `README.md` | Overview and links to language folders |
| Language `README.md` | **Build** and **Run** commands specific to that folder, including executable names |

## Adding a New Example

1. Create a top-level directory with the next available number and a kebab-case name (e.g., `01-hello-world/`).
2. Add a `README.md` describing the concept the example demonstrates.
3. Add `rest/` and/or `terraform/` folders with provisioning for the LaunchDarkly resources the example needs (see [Requirements](#provisioning-launchdarkly-resources)).
4. Create language subdirectories (`python/`, `rust/`, `python-console/`, etc.) for each implementation.
5. Write the code — keep it minimal and well-commented where the concept is non-obvious.
6. Add a `README.md` inside each language folder with run instructions and required `LD_*` environment variables.
7. Add dependency files only if needed.
8. Verify each implementation runs from a clean environment after provisioning.

## Adding a Language to an Existing Example

1. Navigate to the example directory (e.g., `01-hello-world/`).
2. Create the language subdirectory (e.g., `rust/` or `python-console/`).
3. Implement the same concept, matching the behavior of existing implementations. Use the web directory for browser-based apps and the `-console` suffix for terminal-based apps in Python, Node.js, and Java.
4. Add a `README.md` with run instructions.
5. Update the example's top-level `README.md` to reference the new language.

## Code Style

- Match the idiomatic style of each language (PEP 8 for Python, `gofmt` for Go, `rustfmt` for Rust, etc.).
- Prefer clarity over cleverness — these are learning examples.
- Keep examples short: aim for a single concept per example.
- Where possible, include essential comments that describe what the code is doing.
- Implementations of the same example should produce equivalent behavior across languages.

### LaunchDarkly references in code

When code calls LaunchDarkly APIs, SDKs, or evaluates feature flags directly:

1. Add a comment with a **detailed explanation** of what the code is doing and why it matters in this example.
2. Name the **LaunchDarkly capability or feature** involved (for example, "Boolean flag evaluation", "SDK initialization", "REST API — create feature flag").
3. Include a **documentation URL** to the relevant LaunchDarkly docs page.

Example:

```python
# LaunchDarkly capability: Boolean flag evaluation (server-side SDK)
# Evaluates the "new-checkout" flag for the current user context before
# rendering the checkout flow. Returns the configured default when the SDK
# is offline. See: https://launchdarkly.com/docs/sdk/features/evaluating
enabled = client.variation("new-checkout", context, False)
```

## Requirements

Each example documents its own prerequisites in language READMEs. The sections below define the shared baseline for all examples in this repository.

### Language and tooling

Install only what you need for the language and provisioning approach you are working with.

| Language / tool | Minimum version | Notes |
|-----------------|-----------------|-------|
| Python          | 3.12+           | [pyenv](https://github.com/pyenv/pyenv) and `.python-version`; pip in `.venv` |
| Node.js         | 20 LTS+         | [nvm](https://github.com/nvm-sh/nvm) and `.nvmrc` at repository root |
| Java            | 21+             | Maven Wrapper (`./mvnw`) in each Java folder |
| C++             | C++20           | Make and a C++20-capable compiler |
| Go              | 1.22+           | go modules |
| Rust            | 1.75+           | 2021 edition |
| Terraform       | 1.5+            | Required for `terraform/` provisioning examples |
| curl            | any recent      | Required for `rest/` provisioning examples |

Document the exact version used when testing in each language README.

### LaunchDarkly account

You need an active LaunchDarkly account with a project and at least one environment. Create API access tokens and SDK keys from the LaunchDarkly UI. See the [LaunchDarkly docs](https://launchdarkly.com/docs/home) for account setup, SDK credentials, and API access tokens.

Do not commit secrets. Set values locally via environment variables or a local `.env` file that is gitignored.

### Environment variables

All examples use the `LD_*` prefix. Set these before running an example or its provisioning scripts.

#### Core (all examples)

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_API_HOST` | No | LaunchDarkly API base URL. Defaults to `https://app.launchdarkly.com`. Set this for regional instances (for example, the EU instance). |
| `LD_PROJECT_KEY` | Yes | Project key that owns the resources used by the example. |
| `LD_ENVIRONMENT_KEY` | Yes | Environment key within the project (for example, `production`, `test`). |

#### SDK examples

Server-side SDKs authenticate with an SDK key. Client-side and mobile SDKs use different credential types. See [SDK credentials](https://launchdarkly.com/docs/home/account/environment/keys) in the LaunchDarkly docs.

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | For server-side SDKs | Server-side SDK key for the target environment. |
| `LD_CLIENT_SIDE_ID` | For client-side SDKs | Client-side ID for the target environment. |
| `LD_MOBILE_KEY` | For mobile SDKs | Mobile key for the target environment. |

Use only the credential type required by the example.

#### REST API provisioning (`rest/`)

REST examples authenticate with an API access token, not an SDK key. See [Using the LaunchDarkly REST API](https://launchdarkly.com/docs/guides/api/rest-api).

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_API_ACCESS_TOKEN` | Yes | Personal or service token with permissions to create and read the resources in the example. Passed as the `Authorization` header value. |
| `LD_API_VERSION` | No | Value for the `LD-API-Version` request header (for example, `20240415`). Omit to use the version bound to the access token. |

#### Terraform provisioning (`terraform/`)

Terraform examples use the [LaunchDarkly Terraform provider](https://registry.terraform.io/providers/launchdarkly/launchdarkly/latest). Map repository variables to the provider as shown in each example's `terraform/` README.

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_ACCESS_TOKEN` | Yes | API access token for the Terraform provider. Maps to the provider's `access_token` argument (the provider also accepts the native `LAUNCHDARKLY_ACCESS_TOKEN` name; prefer `LD_ACCESS_TOKEN` in this repository for consistency). |
| `LD_API_HOST` | No | Same as above. Maps to the provider's `api_host` argument when not using the default host. |

`LD_PROJECT_KEY` and `LD_ENVIRONMENT_KEY` from the core table are also used in Terraform resource definitions.

Example local setup:

```bash
export LD_API_HOST="https://app.launchdarkly.com"
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="test"
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."   # rest/ examples
export LD_ACCESS_TOKEN="api-..."       # terraform/ examples
```

### Provisioning LaunchDarkly resources

Each example includes the LaunchDarkly resources it needs. Provisioning lives in two optional folders at the example root:

| Folder | Purpose |
|--------|---------|
| `rest/` | Create or configure resources via the [LaunchDarkly REST API](https://launchdarkly.com/docs/guides/api). Typically curl scripts or small language-specific callers. |
| `terraform/` | Create or configure resources via the [LaunchDarkly Terraform provider](https://registry.terraform.io/providers/launchdarkly/launchdarkly/latest). |

Conventions:

- Include a `README.md` in each provisioning folder with prerequisites, required environment variables, and exact commands.
- Keep provisioning minimal — only the flags, segments, environments, or other resources the example requires.
- Run provisioning before the language implementations when the example depends on pre-existing LaunchDarkly state.
- REST examples use `LD_API_ACCESS_TOKEN` and send requests to `$LD_API_HOST/api/v2/...`.
- Terraform examples read `LD_ACCESS_TOKEN` (and optionally `LD_API_HOST`) from the environment; reference `LD_PROJECT_KEY` and `LD_ENVIRONMENT_KEY` in resource blocks or variables.
- Idempotency matters: scripts and Terraform configs should be safe to re-run where possible.

When adding a new example, include `rest/` and/or `terraform/` provisioning if the example cannot run against a blank project without setup.

## Checklists

### Adding a new example

1. Create `NN-<kebab-case-name>/` with the next available number
2. Add top-level `README.md` describing the concept
3. Add `rest/` and/or `terraform/` if LaunchDarkly resources must be provisioned first
4. Create language subdirectories for each implementation
5. Write minimal, well-commented code
6. Add a `README.md` in each language and provisioning folder
7. Add dependency files only where needed
8. Verify each implementation runs from a clean environment after provisioning

### Adding a language to an existing example

1. Navigate to the example directory
2. Create the language subdirectory (e.g. `rust/` or `python-console/`)
3. Implement the same concept with equivalent behavior
4. Use web directories for browser apps; use `-console` for terminal apps in Python, Node.js, and Java
5. Add a language `README.md` with prerequisites, env vars, run steps, and expected behavior
6. Update the example's top-level `README.md` to link the new implementation

## What Does Not Belong Here

- Production application code
- Shared libraries used across examples (keep examples self-contained)
- Large frameworks or boilerplate-heavy setups
- Secrets, credentials, or environment-specific configuration
- Generated build artifacts or vendor directories

## Git Conventions

- Commit messages: imperative mood, concise summary (e.g., `add 01-hello-world example`)
- One example per commit when possible, to keep history reviewable
- Do not commit IDE-specific files beyond the shared `.vscode/settings.json`
