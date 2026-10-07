# Python web

Port **8740**. Checkboxes pick the models. `llama3.2:3b` starts unchecked. **Generate** runs the checked models in order and shows **Running**, then **Finished**. `claude-sonnet` appears when `ANTHROPIC_API_KEY` is set. Each column is a `main.tf`, file counts, `terraform validate`, and the generation metrics. Terraform validate is the emphasized row. Validate still runs when `terraform init` rejects the file, so the issue count includes those errors.

Every model, including Claude, uses `completion_config`, which substitutes `{{ model_name }}` and `{{ variation_key }}`. The provider call is wrapped in `track_metrics_of`. A `claude*` model name calls Anthropic. Anything else calls Ollama.

After validate, `judge_config` on `terraform-codegen-judge` serves the Sonnet prompt. The app calls Anthropic, then `track_judge_result` records the score. Pass and fail files are both scored. Threshold 0.65.

Keywords: **AgentControl** · **judges** · **judge config** · **track_judge_result**

| Topic | Docs |
|-------|------|
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |

Keywords: **AgentControl** · **completion config** · **track_metrics_of**

| Topic | Docs |
|-------|------|
| Python AI SDK | [Python AI SDK](https://launchdarkly.com/docs/sdk/ai/python) |
| Quickstart | [AgentControl quickstart](https://launchdarkly.com/docs/home/agentcontrol/quickstart) |

## Run

```bash
export LD_SDK_KEY="sdk-..."
cd 70-model-demos/04-terraform-codegen/python
python 04-terraform-codegen.py
```

Open **http://127.0.0.1:8740/**. Provision first with [../rest/README.md](../rest/README.md). Ollama and `terraform` need to be on the machine.

What the screen looks like after Generate: [../README.md](../README.md#what-you-will-see).
