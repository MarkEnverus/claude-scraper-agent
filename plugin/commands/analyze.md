---
description: Analyze any data source (API, FTP, website, email) using enhanced BA agent
---

Launch the enhanced business analyst agent to analyze any data source from a URL.

**Supported source types:**
- REST/SOAP APIs
- FTP/SFTP servers
- Email data sources
- Website portals with downloadable data
- Database connection documentation

**Usage:**
```
/scraper-dev:analyze {url}
/scraper-dev:analyze {url} --type website
```

Use the Task tool with subagent_type='scraper-dev:ba-enhanced' to start the analysis.

**CRITICAL**: Do NOT attempt analysis yourself. You MUST invoke the agent using the Task tool. The agent has specialized capabilities for browser automation and multi-protocol testing.
