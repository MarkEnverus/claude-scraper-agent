---
description: Interactive scraper generation workflow
---

Launch the scraper generation workflow by invoking the scraper-generator agent.

Use the Task tool with subagent_type='scraper-dev:scraper-generator' to start the interactive scraper creation process.

CRITICAL: Do NOT attempt to generate scrapers yourself. You MUST invoke the agent using the Task tool. The agent will ask the user all required questions using AskUserQuestion.
