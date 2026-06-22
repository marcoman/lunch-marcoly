# lunch-marcoly

A collection of programming examples, each demonstrating a single concept across multiple languages. Examples are organized by topic — every example gets its own numbered directory, with language implementations nested inside.

## Structure

```
lunch-marcoly/
├── requirements.txt         # Python dependencies (repository-wide)
├── .python-version          # Python version for pyenv (repository-wide)
├── .nvmrc                   # Node.js version for nvm (repository-wide)
├── .venv/                   # Python virtual environment (local)
├── 00-reference/
│   ├── README.md
│   ├── python/              # web application
│   ├── python-console/
│   ├── node/
│   ├── rust/                # console application
│   └── ...
├── 01-hello-world/
│   ├── README.md
│   ├── python/
│   └── rust/
└── ...
```

Examples are prefixed with a two-digit number (`00`, `01`, `02`, …) to control sort order.

## Languages

Each example may include implementations in any of these languages. Python, Node.js, and Java default to **web applications** with a browser UI. Rust and C++ are **console applications**. Optional `-console` variants exist for Python, Node.js, and Java when a terminal-based version is also needed.

| Language | Directory | Application type |
|----------|-----------|------------------|
| Python   | `python/` | Web application |
| Python   | `python-console/` | Console application |
| Node.js  | `node/`   | Web application |
| Node.js  | `node-console/` | Console application |
| Java     | `java/`   | Web application |
| Java     | `java-console/` | Console application |
| C++      | `cpp/`    | Console application |
| Go       | `go/`     | Console application |
| Rust     | `rust/`   | Console application |

## Examples

| # | Directory | Description |
|---|-----------|-------------|
| 00 | [00-reference](00-reference/) | Grid navigator reference app (all languages, no LaunchDarkly) |
| 10 | [10-flag-enablement](10-flag-enablement/) | Grid navigator with LaunchDarkly flags (all languages, Terraform + REST) |
| 11 | [11-flag-variations](11-flag-variations/) | Grid navigator with string, number, JSON, and anonymous flags (all languages) |
| 99 | [99-use-cases](99-use-cases/) | Focused LaunchDarkly use cases (A-B-C-D test, segments, …) |

## Building code

Each implementation **builds locally** in its language folder. Runnable artifacts are named after the **example directory** (e.g. `00-reference.py`, `./00-reference`, `target/00-reference.jar`).

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
| C++      | C++20 compiler and Make |
| Go       | [go.dev](https://go.dev/dl/) 1.22+ |
| Rust     | [rustup.rs](https://rustup.rs/) 1.75+ |

### Build patterns (from each language folder)

| Language | Build | Run (artifact name varies by example) |
|----------|-------|---------------------------------------|
| Python | *(no compile step)* | `python 00-reference.py` |
| Node.js | `npm install` *(when deps exist)* | `node 00-reference.js` |
| Java | `./mvnw clean install` | `java -jar target/00-reference.jar` |
| C++ | `make clean && make all` | `./00-reference` |
| Go | `go build -o 00-reference .` | `./00-reference` |
| Rust | `cargo build --release` | `./target/release/00-reference` |

Each language folder's `README.md` lists the exact **Build** and **Run** commands for that implementation.

## Quick Start

1. Clone the repository.
2. Set up Python with [pyenv](#python-and-pyenv) and other toolchains as needed (see [Building code](#building-code)).
3. Open an example (e.g. [00-reference](00-reference/)).
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
