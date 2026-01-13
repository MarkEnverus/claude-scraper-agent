"""Phase 1.5: Parameter Analysis Handler.

After Phase 1 discovers operations with basic parameter info,
this phase deeply analyzes parameters to extract:
- Date/time format patterns
- Examples and defaults
- Enum values and constraints
- Required vs optional distinctions

This handler uses LLM-based analysis to enrich parameter metadata
for accurate scraper generation.
"""

import logging
import json
from typing import Dict, Any, List
from agentic_scraper.business_analyst.state import BAAnalystState, EndpointFinding
from agentic_scraper.llm.factory import LLMFactory
from agentic_scraper.business_analyst.prompts.param_analysis import parameter_analysis_prompt

logger = logging.getLogger(__name__)


def param_p15_handler(state: BAAnalystState) -> Dict[str, Any]:
    """Phase 1.5: Analyze parameters for discovered endpoints.

    Takes endpoints from Phase 1 (with basic parameter info) and enriches
    them with detailed metadata using LLM analysis.

    Args:
        state: Current graph state with endpoints from Phase 1

    Returns:
        State updates with enriched endpoint parameters
    """
    logger.info("=== Phase 1.5: Parameter Analysis ===")

    endpoints = state.get('endpoints', [])
    if not endpoints:
        logger.warning("No endpoints to analyze parameters for")
        return {
            'p15_complete': True,
            'next_action': 'continue'
        }

    # Check if parameter analysis is enabled
    config = state.get('config')
    if config and not getattr(config, 'enable_parameter_analysis', True):
        logger.info("Parameter analysis disabled in config, skipping Phase 1.5")
        return {
            'p15_complete': True,
            'next_action': 'continue'
        }

    factory = LLMFactory(config=config, region=config.aws_region if config else 'us-east-1')
    llm = factory.create_reasoning_model()  # Use reasoning model for deep analysis

    enriched_endpoints = []

    for endpoint in endpoints:
        # Skip if no parameters
        if not endpoint.parameters:
            logger.debug(f"No parameters for endpoint {endpoint.name}, skipping enrichment")
            enriched_endpoints.append(endpoint)
            continue

        # Generate parameter analysis prompt
        prompt = parameter_analysis_prompt(
            endpoint_name=endpoint.name,
            endpoint_url=endpoint.url,
            method=endpoint.method_guess,
            basic_parameters=endpoint.parameters,
            description=endpoint.notes,
            format=endpoint.format
        )

        try:
            logger.info(f"Analyzing {len(endpoint.parameters)} parameters for: {endpoint.name}")
            response = llm.invoke(prompt)

            # Parse LLM response (JSON with enriched parameters)
            response_text = response.content if hasattr(response, 'content') else str(response)

            # Strip markdown code blocks if present
            if response_text.strip().startswith("```"):
                lines = response_text.strip().split('\n')
                # Remove first line (```json) and last line (```)
                if len(lines) > 2:
                    response_text = '\n'.join(lines[1:-1])

            enriched_params = json.loads(response_text)

            # Update endpoint with enriched parameters
            if 'parameters' in enriched_params:
                endpoint.parameters = enriched_params['parameters']
                logger.info(f"✅ Enriched {len(endpoint.parameters)} parameters for {endpoint.name}")
            else:
                logger.warning(f"LLM response missing 'parameters' key for {endpoint.name}")

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response for {endpoint.name}: {e}")
            logger.debug(f"Response text: {response_text[:200]}...")
            # Keep basic parameters if enrichment fails
        except Exception as e:
            logger.warning(f"Failed to enrich parameters for {endpoint.name}: {e}")
            # Keep basic parameters if enrichment fails

        enriched_endpoints.append(endpoint)

    # Log summary
    total_params = sum(len(ep.parameters) for ep in enriched_endpoints)
    logger.info(f"✅ Phase 1.5 complete: Analyzed {total_params} parameters across {len(enriched_endpoints)} endpoints")

    return {
        'endpoints': enriched_endpoints,
        'p15_complete': True,
        'next_action': 'continue'
    }


# Export
__all__ = ["param_p15_handler"]
