# Archived Documentation

This directory contains obsolete design documents from before the BA agent migration to Python CLI.

## Archived Files

### AGENT_VALIDATION_FIX.md (Dec 5, 2024)
- **Status**: Obsolete
- **Reason**: Describes the old ba-enhanced.md agent's 3-phase validation approach
- **Current Implementation**: Python CLI with 4-phase validation (see `claude_scraper/agents/ba_analyzer.py`)
- **References**: `plugin/agents/ba-enhanced.md` (deleted)

### AGENT_CORE.md (Dec 8, 2024)
- **Status**: Unimplemented proposal
- **Reason**: Proposes AWS Bedrock Agent Core for hosting AI agents
- **Current Implementation**: Python CLI with LangGraph orchestration
- **References**: ba-enhanced agent that no longer exists

### LANCEDB_PLUGIN_INTEGRATION.md (Dec 8, 2024)
- **Status**: Unimplemented proposal
- **Reason**: Proposes LanceDB integration for historical context search
- **Current Implementation**: Not implemented
- **References**: `plugin/agents/ba-enhanced.md` (deleted), scraper-generator.md, scraper-fixer.md

## Migration Status

All ba-enhanced agent code has been removed and replaced with Python CLI:
- **Removed**: 3,288 lines of legacy agent code (ba-enhanced.md, ba-validator.md, ba-collator.md)
- **Replaced with**: Python CLI using BAML, LangGraph, Botasaurus
- **See**: `MIGRATION_STATUS.md` for complete migration details

---

**Note**: These documents are preserved for historical reference only. They describe architecture that no longer exists.
