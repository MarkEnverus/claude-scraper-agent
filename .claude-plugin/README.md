# Scraper Agent Marketplace

This directory contains the Claude Code marketplace configuration for the Scraper Agent plugin.

## Installation

Users can install this plugin directly from GitHub:

```bash
# Add the marketplace
claude plugin marketplace add https://github.com/yourusername/claude_scraper_agent

# Install the plugin
claude plugin install scraper-dev@scraper-agent-marketplace

# Restart Claude Code
```

## Marketplace Structure

- `marketplace.json` - Marketplace manifest that defines available plugins
- Points to `../plugin/` directory which contains the actual plugin files

## Plugin Contents

The scraper-dev plugin includes:
- 5 specialized agents for scraper generation
- 1 slash command (`/create-scraper`)
- 1 skill for scraper creation logic
- Support for HTTP/REST, website parsing, FTP, and email collection methods
