# 04-terraform-codegen

Compare selected code generators on one LaunchDarkly Terraform brief. Python web on **:8740**. The screen is the product. This file is the contract.

## Click

Checkboxes pick the models. One **Generate** runs them in order. Each selected model evaluates `terraform-codegen-compare`:

1. Context key `codegen-1b` → variation `local-1b` → `llama3.2:1b` (inexpensive, checked)
2. Context key `codegen-8b` → variation `local-8b` → `llama3.1:8b` (local ceiling, checked)
3. Fallthrough context `codegen-3b` → variation `local-3b` → `llama3.2:3b` (unchecked)
4. Context key `codegen-haiku` → variation `claude-haiku` → `claude-haiku-4-5-20251001` (smaller hosted, checked)
5. Context key `codegen-sonnet` → variation `claude-sonnet` → `claude-sonnet-5` (reference, checked)

After validate, `terraform-codegen-judge` scores the file with Sonnet. Pass and fail files are both scored. The pass line is 0.65. The score and a short reason appear on the column. The file is not rewritten. **LD details** keeps each model's sent and received record, including the judge prompt.

Screenshots of that screen are in [README.md](README.md): the comparison table, the file panels, and the Received tab.

`claude-sonnet` is offered when `ANTHROPIC_API_KEY` is set. AgentControl serves the variation and substitutes the prompt. The app calls Anthropic inside `track_metrics_of`, so duration, tokens, and generation success are recorded the same way as the local models. If that variation is not served, the column errors and points at `rest/add-claude-variation.sh`. `local-8b` does the same for `rest/add-local-8b-variation.sh`.

The header shows **Running** after Generate is pressed and **Finished** when every selected model has been written and validated.

The SDK fills `{{ model_name }}` and `{{ variation_key }}` in the user message. The model is told to copy those into the first line:

```text
# ancestry: model=llama3.2:1b variation=local-1b
```

That comment is the intended diff. Resource keys are the same in both files.

## File

One `main.tf` per model, written to `output/<model-id>/main.tf`. A colon in the model id becomes a hyphen, so `llama3.2:1b` lands in `output/llama3.2-1b/`. Each Generate overwrites that folder. `output/` is untracked.

The file contains:

- Provider `launchdarkly/launchdarkly` `~> 2.0`, plus `access_token`, `project_key`, and `environment_key` variables. No hardcoded project or token.
- Boolean flag `codegen-release` and string flag `codegen-plan`.
- A `launchdarkly_feature_flag_environment` for each flag: on, fallthrough variation 0.
- Six segments, name and description only: `codegen-size-small`, `codegen-size-medium`, `codegen-size-large`, `codegen-cohort-internal`, `codegen-cohort-external`, `codegen-cohort-beta`. Each still sets `env_key`, because the provider requires it.
- Three custom metrics: `codegen-latency` (numeric milliseconds), `codegen-error-rate` (numeric percent), `codegen-thumbs` (numeric count). Each has `event_key` and `randomization_units`.

Descriptions are the model's, derived from the resource name.

After the write, the app runs `terraform init -backend=false` and `terraform validate -json` in that folder. Validate does not call LaunchDarkly and does not apply. A failure still leaves `main.tf` on disk. The JSON `error_count` plus `warning_count` is the issue count. The file is also counted: lines, `resource` blocks (target 13), `description` attributes (target 11), and whether the first line is the ancestry comment.

## Generation metrics

`track_metrics_of` records duration, time to first token, input tokens, output tokens, total tokens, and generation success for every served model, including Claude. That success means the model call finished. Terraform validate is a separate pass or fail. The comparison table marks the better value green and the worse value red across however many models are checked. Lower time, input tokens, total tokens, cost, and validate issues win. Resources closer to 13 and descriptions closer to 11 win. Pass beats fail. Lines and output tokens have no winner. The Python SDK summary has no cost field. The screen prints a cost or price parameter when the served model config has one, and leaves cost blank otherwise. No multiplication into a per-token price.

## Out of this version

- `terraform apply`
- A judge or a score
- A series portal
- A second language
- Segment rules, included contexts, and tags

Segment options for a later revision: a rule clause such as `size is small`, an included context list, or tags.

Claude's price shows when the served model config carries a cost or price parameter. Same click.
