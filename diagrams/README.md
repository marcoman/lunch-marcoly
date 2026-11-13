# diagrams

Two maps of where the examples in this repository fit into real work.

| File | What it maps |
|------|--------------|
| [cicd-pipeline.html](cicd-pipeline.html) | **Anatomy of a CI/CD Pipeline** — five stages, from a pull request to a retired flag |
| [llm-workflow.html](llm-workflow.html) | **Anatomy of an LLM Workflow** — six steps, from an incoming request to a checked answer |

Each diagram has two layers. The top layer is the workflow itself: a stage, the
choice it hides, and the LaunchDarkly capability that owns that choice. The second
layer, directly beneath each stage, names the examples here that demonstrate it.
**Every citation is a link to its folder.**

Open either file from a clone — they are plain HTML with no build step and no
external files, so a browser is enough. GitHub shows `.html` as source rather than
rendering it.

## Reading a citation

A citation is the top-level folder number, a slash, and the example number:

```
10/105   ->  10-feature-management/105-prerequisite-flags
20/204   ->  20-agent-management/204-agent-judges
99/15    ->  99-use-cases/15-guarded-rollout
```

Numbers in blue are built. **Muted numbers are stubs** — the folder exists and the
example does not work yet. An example that fits more than one stage is cited at
each of them: `99/16` adaptive triggers is both a release control and a monitoring
one, so it appears under Release and under Monitor.

The three `0x-reference-*` folders carry no citation. They are the baselines with
no LaunchDarkly in them, and the diagrams name them in a footnote instead.

## Regenerating

```bash
python3 diagrams/build.py            # rewrite both .html files
python3 diagrams/build.py --check    # report unmapped examples, write nothing
```

`build.py` reads the example folders on every run, so the list of examples and
which of them are stubs always follow the repository. **Where** an example lands is
editorial and lives in the `PLACEMENT` table at the top of the script — one entry
per numbered example, giving its CI/CD stages and its LLM steps, either of which
may be empty.

Add an example to the repository and `--check` names it as unmapped until it has a
`PLACEMENT` entry. Rename or remove one and `--check` reports it as a ghost. Run
the check before a release so the diagrams do not quietly fall behind the code.

Both files are generated. Edit `build.py`, not the HTML.
