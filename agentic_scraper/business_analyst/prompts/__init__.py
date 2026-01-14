"""Prompts for BA Analyst phases.

This package contains prompt templates for each phase of the BA Analyst:
- Phase 0: Data source detection and iterative discovery
- Phase 1: Documentation and metadata extraction
- Phase 2: Live endpoint testing and validation
- Phase 3: Validated specification generation

Each phase has dedicated prompt functions that format analysis instructions
for Claude with the appropriate context and constraints.
"""

from agentic_scraper.business_analyst.prompts.phase0 import (
    phase0_single_page_prompt,
    phase0_iterative_prompt,
    phase0_qa_validation_prompt,
)

from agentic_scraper.business_analyst.prompts.phase1 import (
    phase1_documentation_prompt,
    analyze_endpoint_prompt,
)

from agentic_scraper.business_analyst.prompts.phase2 import (
    phase2_testing_prompt,
)

from agentic_scraper.business_analyst.prompts.phase3 import (
    phase3_validation_prompt,
    executive_summary_prompt,
)

from agentic_scraper.business_analyst.prompts.link_reranking import (
    link_reranking_prompt,
)

__all__ = [
    # Phase 0
    'phase0_single_page_prompt',
    'phase0_iterative_prompt',
    'phase0_qa_validation_prompt',
    # Phase 1
    'phase1_documentation_prompt',
    'analyze_endpoint_prompt',
    # Phase 2
    'phase2_testing_prompt',
    # Phase 3
    'phase3_validation_prompt',
    'executive_summary_prompt',
    # Link reranking
    'link_reranking_prompt',
]
