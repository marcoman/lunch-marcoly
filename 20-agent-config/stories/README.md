# Series stories cache

Shared Yahoo Finance headline cache for AgentControl examples **21–24**.

```text
20-agent-config/stories/stories_cache.json
```

All language ports under each example read and write this file. Per-example
`rest/messages/` stay local to each lesson; only the news cache is shared so
Get Stories (and Yahoo 429 fallbacks) work across the portal tabs.

Seeded from a prior successful fetch; refresh by clicking **Get Stories** in any
example UI.
