"""LLM prompt for Phase 1.5 parameter analysis.

Extracts detailed parameter metadata including date formats,
examples, defaults, and constraints from API operation parameters.
"""

import json
from typing import List, Dict, Any


def parameter_analysis_prompt(
    endpoint_name: str,
    endpoint_url: str,
    method: str,
    basic_parameters: List[Dict],
    description: str,
    format: str
) -> str:
    """Generate prompt for LLM to analyze parameters in detail.

    Args:
        endpoint_name: Operation name
        endpoint_url: Full endpoint URL
        method: HTTP method
        basic_parameters: Basic param info (name, type, required)
        description: Operation description
        format: Response format

    Returns:
        Prompt string for LLM with JSON response schema
    """

    params_json = json.dumps(basic_parameters, indent=2)

    prompt = f"""You are analyzing API endpoint parameters to extract detailed metadata for scraper generation.

# Endpoint Information

**Name**: {endpoint_name}
**URL**: {endpoint_url}
**Method**: {method}
**Response Format**: {format}
**Description**: {description}

# Basic Parameters (from API spec)

{params_json}

# Your Task

For each parameter, extract DETAILED metadata by analyzing:
1. **Type inference**: If type is "string" but name suggests date/time, infer correct type
2. **Format patterns**: Extract date/time format (YYYY-MM-DD, ISO-8601, unix_timestamp)
3. **Examples**: Provide realistic example values
4. **Defaults**: Infer default values from description (e.g., "defaults to today")
5. **Constraints**: Extract enum values, min/max, patterns from description
6. **Location**: Confirm if query, path, header, or body parameter

# Special Focus on Date/Time Parameters

For parameters with date/time types:
- **Format**: Extract exact pattern (YYYY-MM-DD, MM/DD/YYYY, ISO-8601, etc.)
- **Example**: Provide example matching the format ("2024-01-15", "2024-01-15T00:00:00Z")
- **Default**: Common defaults are "today", "yesterday", "first day of month", etc.
- **Range**: If there's a valid date range, note it (e.g., "last 90 days only")

# Response Format

Return **ONLY** valid JSON (no markdown, no explanations outside JSON):

{{
  "parameters": [
    {{
      "name": "market_date",
      "type": "date",
      "required": true,
      "description": "Market date for pricing data",
      "location": "query",
      "format": "YYYY-MM-DD",
      "example": "2024-01-15",
      "default": null,
      "enum": null,
      "minimum": null,
      "maximum": null,
      "pattern": "^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$"
    }},
    {{
      "name": "location_id",
      "type": "string",
      "required": false,
      "description": "Optional location identifier",
      "location": "query",
      "format": null,
      "example": "ZONE.MIDWEST",
      "default": null,
      "enum": null,
      "minimum": null,
      "maximum": null,
      "pattern": null
    }},
    {{
      "name": "market_type",
      "type": "string",
      "required": false,
      "description": "Market type selection",
      "location": "query",
      "format": null,
      "example": "DA",
      "default": "DA",
      "enum": ["DA", "RT", "EX_ANTE", "EX_POST"],
      "minimum": null,
      "maximum": null,
      "pattern": null
    }}
  ]
}}

# Important Rules

1. **Type accuracy**: "market_date" should be type "date", not "string"
2. **Format patterns**: Use standard notations (YYYY-MM-DD, ISO-8601, unix_timestamp)
3. **Realistic examples**: Provide actual example values, not placeholders
4. **Infer from context**: If description says "defaults to current date", set default accordingly
5. **Preserve all parameters**: Return all parameters from input, even if not enriched
6. **Use null for unknown**: If a field cannot be inferred, use null (not empty string)

Begin analysis now. Return ONLY the JSON response.
"""

    return prompt
