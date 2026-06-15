# 00-reference

The reference example for **lunch-marcoly**: a grid navigator app and template for repository conventions.

## What this demonstrates

### Application

A username-only login followed by a **3×3 grid navigator**. See [application.md](application.md) for full behavior and acceptance criteria. Selection is **`X` only** — no highlight colors.

### Repository conventions

How examples are organized — numbering, language directories, web vs console apps, and build patterns. See [project.md](../project.md).

## Prerequisites

No LaunchDarkly account required. This example is **reference-only** — it does not integrate with LaunchDarkly. Feature flags live in [10-flag-enablement](../10-flag-enablement/).

Set up the repository once ([pyenv](https://github.com/pyenv/pyenv) for Python, [nvm](https://github.com/nvm-sh/nvm) for Node, other toolchains) using the [root README](../README.md#building-code).

## Build and run

Each implementation builds **locally** in its language folder. Artifacts are named **`00-reference`** (or `00-reference.py` / `00-reference.js` / `00-reference.jar`).

| Language | Directory | Build | Run |
|----------|-----------|-------|-----|
| Python (web) | [python/](python/) | *(see README)* | `python 00-reference.py` |
| Python (console) | [python-console/](python-console/) | *(see README)* | `python 00-reference.py` |
| Node.js (web) | [node/](node/) | `npm install` | `node 00-reference.js` |
| Node.js (console) | [node-console/](node-console/) | `npm install` | `node 00-reference.js` |
| Java (web) | [java/](java/) | `./mvnw clean install` | `java -jar target/00-reference.jar` |
| Java (console) | [java-console/](java-console/) | `./mvnw clean install` | `java -jar target/00-reference.jar` |
| C++ | [cpp/](cpp/) | `make clean && make all` | `./00-reference` |
| Go | [go/](go/) | `go build -o 00-reference .` | `./00-reference` |
| Rust | [rust/](rust/) | `cargo build --release` | `./target/release/00-reference` |

Open the language README for full **Build**, **Run**, and **What to expect** sections.

## Language implementations

| Language | Directory | Application type | Status |
|----------|-----------|------------------|--------|
| Python | [python/](python/) | Web application | Done |
| Python | [python-console/](python-console/) | Console application | Done |
| Node.js | [node/](node/) | Web application | Done |
| Node.js | [node-console/](node-console/) | Console application | Done |
| Java | [java/](java/) | Web application | Done |
| Java | [java-console/](java-console/) | Console application | Done |
| C++ | [cpp/](cpp/) | Console application | Done |
| Go | [go/](go/) | Console application | Done |
| Rust | [rust/](rust/) | Console application | Done |

## Further reading

- [application.md](application.md) — grid navigator behavior and acceptance criteria
- [project.md](../project.md) — repository layout, build conventions, and conventions
- [README.md](../README.md) — repository overview
