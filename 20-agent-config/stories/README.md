# Series stories cache

Shared headline cache for AgentControl examples **21–26** and
[`20-capstone`](../20-capstone/).

```text
20-agent-config/stories/stories_cache.json
```

All language ports under each example read and write this file. The capstone
also returns its last usable pair from `/api/bootstrap`, restoring stories after
a Node process or browser restart. Per-example `rest/messages/` stay local to
each lesson; only the news cache is shared.

Seeded from a prior successful fetch; refresh by clicking **Get Stories** in any
example UI.
