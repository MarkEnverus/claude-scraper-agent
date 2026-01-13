"""Prompts for BA Executive Summary Generator - Markdown summary generation.

Migrated from baml_src/ba_executive_summary.baml to Python.
Each function returns a formatted prompt string for Claude.
"""

from typing import Any


def generate_executive_summary_prompt(validated_spec: Any) -> str:
    """Executive summary generation prompt.

    Original: baml_src/ba_executive_summary.baml -> GenerateExecutiveSummary()

    Args:
        validated_spec: Complete validated specification

    Returns:
        Formatted prompt string for Claude
    """
    # Extract key fields for the prompt
    source = validated_spec.source
    source_type = validated_spec.source_type
    timestamp = validated_spec.timestamp
    total_endpoints = validated_spec.executive_summary.total_endpoints_discovered
    accessible_endpoints = validated_spec.executive_summary.accessible_endpoints
    auth_required = validated_spec.authentication.required if hasattr(validated_spec, 'authentication') else False
    auth_method = validated_spec.authentication.method if (hasattr(validated_spec, 'authentication') and auth_required) else "N/A"
    success_rate = validated_spec.executive_summary.success_rate
    confidence_score = validated_spec.validation_summary.confidence_score
    confidence_level = validated_spec.validation_summary.confidence_level
    scraper_type = validated_spec.scraper_recommendation.type
    complexity = validated_spec.scraper_recommendation.complexity
    estimated_effort = validated_spec.scraper_recommendation.estimated_effort

    # Build the full specification as a formatted string
    spec_text = str(validated_spec)

    return f"""You are generating an executive summary for business stakeholders
reviewing a data source specification analysis.

This summary will be used for JIRA tickets, stakeholder communication,
and documentation. It must be clear, comprehensive, and actionable.

## Validated Specification:
{spec_text}

## Your Task: Generate Executive Summary in Markdown

Create a comprehensive, JIRA-ready markdown document with these sections:

### 1. Main Title and Executive Summary

Start with a title:
```
# {source} - Data Source Analysis
```

Then add an Executive Summary paragraph with:
- **Data Source**: {source}
- **Source Type**: {source_type}
- **Analysis Date**: {timestamp}
- **Total Endpoints/Datasets Discovered**: {total_endpoints}
- **Accessible Without Auth**: {accessible_endpoints}
- **Authentication Required**: {"Yes" if auth_required else "No"}
{f"- **Auth Method**: {auth_method}" if auth_required else ""}
- **Success Rate**: {success_rate}
- **Confidence Score**: {confidence_score} ({confidence_level})
- **Recommended Scraper**: {scraper_type}
- **Estimated Complexity**: {complexity}
- **Estimated Effort**: {estimated_effort}

### 2. Endpoint Inventory

Create a markdown table with ALL endpoints from validated_spec.endpoints array:

```markdown
## Endpoint Inventory

| Endpoint ID | Name | Method | Path | Auth Required | Response Format | Status | Update Frequency |
|-------------|------|--------|------|---------------|-----------------|--------|------------------|
```

For EACH endpoint in validated_spec.endpoints:
- **Endpoint ID**: Use endpoint.endpoint_id
- **Name**: Use endpoint.name (truncate to 40 chars if too long)
- **Method**: Use endpoint.method (GET, POST, etc.)
- **Path**: Use endpoint.path (truncate to 60 chars if too long, add "..." if truncated)
- **Auth Required**: "Yes" if endpoint.authentication.get('required') == "true" else "No"
- **Response Format**: Use endpoint.response_format (JSON, XML, CSV, etc.)
- **Status**: Map endpoint.validation_status to human-readable with emoji:
  * TESTED_200_OK → "✅ Accessible"
  * TESTED_401_UNAUTHORIZED → "🔒 Auth Required"
  * TESTED_403_FORBIDDEN → "🔒 Forbidden"
  * TESTED_404_NOT_FOUND → "❌ Not Found"
  * NOT_TESTED → "⚠️ Not Tested"
  * Any other value → "⚠️ Unknown"
- **Update Frequency**: Use endpoint.update_frequency or "Unknown"

CRITICAL: Include ALL endpoints - do NOT summarize or truncate the list.

After the table, add a summary line:
```
**Total Endpoints**: {{number of endpoints}}
```

### 3. Authentication & Access Requirements

```markdown
## Authentication & Access Requirements
```

If authentication is required:
- **Authentication Required**: Yes
- **Method**: {{auth method}}
- **Header Name**: `{{header name if available}}`
- **Registration URL**: {{registration URL if available}}
- **Evidence**: {{first 300 chars of evidence}}

**Access Steps**:
1. Register for API credentials at the registration URL above
2. Obtain API key/token
3. Include authentication header in all requests
4. Test with real credentials to confirm access

If no authentication required:
- **Authentication Required**: No
- **Public Access**: Endpoints are publicly accessible without authentication

If access_requirements exist, include:
- **Rate Limits**: {{rate limits}}
- **Terms of Use**: {{terms URL}}

### 4. Key Findings

```markdown
## Key Findings
```

Include validation summary:
- **Phases Completed**: {{number}} phases
- **Documentation Review**: {{summary}}
- **Live API Testing**: {{summary}}
- **Discrepancies Found**: {{count}}
- **Confidence Score**: {{score}} ({{level}})

If collation_metadata exists:
- **Analysis Type**: Multi-run collation (Run 1 + Run 2)
- **Run 1 Confidence**: {{score}}
- **Run 2 Confidence**: {{score}}
- **Final Confidence**: {{score}} (weighted 30%/70%)
- **Confidence Consistency**: {{consistency}}

If improvements_from_run1 exist, document them.

If discrepancies exist, list them with severity and resolution.

### 5. Scraper Implementation Plan

```markdown
## Scraper Implementation Plan
```

**Recommended Approach**: {{scraper type}}

**Complexity**: {{complexity}}

**Estimated Effort**: {{effort}}

**Rationale**:
{{list each rationale point}}

**Key Challenges**:
{{list each challenge or "No significant challenges identified"}}

### 6. Next Steps

```markdown
## Next Steps
```

List next_steps from the spec, or default to:
1. Feed validated_datasource_spec.json to scraper generator
2. Implement scraper based on recommendations above
3. Test with sample data
4. Deploy to production

---

**Analysis Artifacts**:
{{list all artifacts_generated}}

---

*Generated by BA Agent v2.0 - Automated Business Analyst*

## Output Requirements:

1. **Return ONLY the markdown text** - NO JSON, NO code blocks, NO wrapping
2. Use proper markdown formatting:
   - `#` for main title
   - `##` for section headers
   - `|` for tables with proper alignment
   - `-` for bullet lists
   - `**` for bold emphasis
   - Emoji indicators: ✅ ❌ 🔒 ⚠️
3. Keep tables readable (max 120 chars per row, truncate long values)
4. Include ALL endpoints in the table (do not summarize or truncate)
5. Make it JIRA/Confluence compatible (standard markdown)
6. Ensure the output is ready to copy-paste into JIRA tickets

CRITICAL:
- Return the raw markdown text directly
- DO NOT wrap it in ```markdown code blocks
- DO NOT return it as a JSON string
- DO NOT add any preamble or explanation
- Just return the markdown content itself"""
