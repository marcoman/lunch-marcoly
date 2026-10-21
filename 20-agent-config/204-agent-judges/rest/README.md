# 24-agent-judges — REST provisioning

Preferred path to create:

| Resource | Key | Mode |
|----------|-----|------|
| Completion config | `equity-briefing-judged` | completion |
| Source Fidelity Judge | `equity-briefing-source-fidelity` | judge |
| Recommendation Discipline Judge | `equity-briefing-recommendation-discipline` | judge |

## Scripts

| Script | Purpose |
|--------|---------|
| [create-judges.sh](create-judges.sh) | Both custom judges (Ollama `llama3.2:3b`) |
| [update-judge-messages.sh](update-judge-messages.sh) | PATCH judge system prompts from `messages/` |
| [update-judge-temperature.sh](update-judge-temperature.sh) | Pin both judges to `temperature: 0` |
| [update-charlie-model.sh](update-charlie-model.sh) | Point `concise-skeptic` at rewrite model (`llama3.1:8b`) |
| [create-config.sh](create-config.sh) | Completion config + Toby/Charlie variations + targeting |
| [get-judges-status.sh](get-judges-status.sh) | Demo health: judges · variations · targeting · generations (`--verbose` links) |
| [update-name-targeting.sh](update-name-targeting.sh) | Charlie → skeptic, Toby → reckless |
| [update-targeting.sh](update-targeting.sh) | Fallthrough helper |
| [create-model-config.sh](create-model-config.sh) | Custom Ollama model configs |
| [delete-config.sh](delete-config.sh) | Delete a config by key |
| [get-config.sh](get-config.sh) | Inspect a config |

Message sources: [messages/](messages/).

## Order

```bash
export LD_API_ACCESS_TOKEN=...
export LD_PROJECT_KEY=lunch-marcoly
export LD_ENVIRONMENT_KEY=test

./create-judges.sh
./create-config.sh
```

Normative behavior: [../application.md](../application.md).
