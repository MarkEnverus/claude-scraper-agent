"""Prompts for BA Collator agent - Merging analysis runs with weighted scoring.

Migrated from baml_src/ba_collator.baml to Python.
Each function returns a formatted prompt string for Claude.
"""

from typing import Any


def merge_phase0_prompt(run1: Any, run2: Any, run2_focus_areas: list[str]) -> str:
    """Phase 0 collation prompt - merge detection results from two runs.

    Original: baml_src/ba_collator.baml -> MergePhase0()

    Args:
        run1: Phase 0 detection from Run 1
        run2: Phase 0 detection from Run 2
        run2_focus_areas: Areas Run 2 focused on

    Returns:
        Formatted prompt string for Claude
    """
    focus_areas_text = "\n".join(f"  - {area}" for area in run2_focus_areas)

    return f"""You are merging two Phase 0 data source detection analysis runs.

## Run 1 Result (30% weight - initial discovery):
{run1}

## Run 2 Result (70% weight - focused re-analysis):
{run2}

## Run 2 Focus Areas:
{focus_areas_text}

## Your Task: Merge the Detection Results

Apply these weighted merge rules:

1. **Detected Type**: If Run 2 has higher confidence, prefer Run 2's detection.
   Otherwise, verify both agree.

2. **Confidence Score**: Calculate weighted average:
   - Final confidence = (0.3 × Run1 confidence) + (0.7 × Run2 confidence)
   - If both runs highly agree (difference < 0.1), add bonus +0.05 (max 1.0)

3. **Indicators**: Merge both lists, keeping unique indicators from both runs.
   Run 2 indicators should be prioritized as they're from focused analysis.

4. **Discovered API Calls**: Combine all unique URLs/calls from both runs.
   Deduplicate but preserve all discoveries.

5. **Endpoints**: Merge endpoint lists. If same endpoint appears in both runs,
   prefer Run 2's details (higher weight).

6. **URL**: Should be identical in both runs. If different, prefer Run 2.

7. **Fallback Strategy**: Take from Run 2 if present, otherwise Run 1.

## Output Requirements:

Return a merged Phase0Detection with:
- detected_type: The agreed-upon or highest-confidence type
- confidence: Weighted score (0.3 × run1 + 0.7 × run2)
- indicators: Combined unique indicators from both runs
- discovered_api_calls: All unique API calls from both runs
- discovered_endpoint_urls: Merged endpoint URLs (Run 2 preferred for conflicts)
- auth_method: From Run 2 if available
- base_url: From Run 2 if available
- url: The data source URL
- fallback_strategy: From Run 2 if available

Return your merged result as JSON matching the Phase0Detection schema."""


def merge_complete_specs_prompt(run1: Any, run2: Any) -> str:
    """Complete specification collation prompt - merge validated specs from two runs.

    Original: baml_src/ba_collator.baml -> MergeCompleteSpecs()

    Args:
        run1: Validated specification from Run 1
        run2: Validated specification from Run 2

    Returns:
        Formatted prompt string for Claude
    """
    return f"""You are merging two complete Business Analyst analysis runs into a final,
definitive data source specification.

## Run 1 Specification (30% weight - initial analysis):
{run1}

## Run 2 Specification (70% weight - validator-guided focused analysis):
{run2}

## Your Task: Create the Final Merged Specification

Apply these weighted merge rules for each section:

### 1. Executive Summary
- total_endpoints_discovered: Use Run 2 count only (Run 2 is source of truth)
- accessible_endpoints: Use Run 2
- success_rate: Use Run 2
- primary_formats: Merge unique formats from both runs
- authentication_required: If runs disagree, prefer Run 2
- estimated_scraper_complexity: Use Run 2
- **NEW**: Add improvements_from_run1 field documenting what Run 2 improved
- **NEW**: Add endpoints_excluded_from_run1: Count of Run 1-only endpoints excluded
- **NEW**: Add filtering_applied: true
- **NEW**: Add filtering_reason: "Run 1 endpoints not validated in Run 2 were excluded"

### 2. Validation Summary
- phases_completed: Should be same for both
- confidence_score: Calculate using this formula:
  1. Base weighted average: (0.3 × Run1 confidence) + (0.7 × Run2 confidence)
  2. Consistency bonus: If |Run1 - Run2| < 0.1, add +0.05 (max 1.0)
  3. Critical gaps deduction: If validation_report.critical_gaps_count > 0, subtract 0.1 (min 0.0)
  Example: Run1=0.85, Run2=0.90, difference=0.05 → Base=0.885, +0.05 bonus = 0.935
- confidence_level: Based on final confidence (>0.8=HIGH, 0.6-0.8=MEDIUM, <0.6=LOW)
- discrepancies_found: Sum of unique discrepancies from both runs
- **NEW**: Add these collation fields:
  - collation_complete: true
  - runs_analyzed: 2
  - final_confidence_score: <weighted average>
  - run1_confidence: <from run1>
  - run2_confidence: <from run2>
  - confidence_consistency: "improved" | "consistent" | "declined"
  - validator_status: "pass" | "needs_improvement" | "fail"
  - discrepancies_resolved: <count of conflicts resolved>

### 3. Endpoints List

Endpoint Matching Rules:
- Match endpoints by endpoint_id (primary key)
- If endpoint_id is same, consider it the same endpoint across runs
- For each Run 2 endpoint:
  1. Find corresponding Run 1 endpoint by matching endpoint_id
  2. If found: Mark tested_in_run1=true, tested_in_run2=true
  3. If not found: Mark tested_in_run1=false, tested_in_run2=true
- For each Run 1 endpoint NOT in Run 2:
  1. DO NOT include in final spec (not validated by Run 2)
  2. Track count in collation_metadata.endpoints_excluded_from_run1

Endpoint Merging Process:
- Start with ONLY endpoints from Run 2 (source of truth when Run 2 is required)
- For each Run 2 endpoint, check if it exists in Run 1:
  - If yes: Mark tested_in_run1=true, tested_in_run2=true,
    validation_consistency=<true if status matches>
  - If no: Mark tested_in_run1=false, tested_in_run2=true,
    validation_consistency="new_in_run2"
- Run 1-only endpoints are NOT included (Run 2 is the validation pass)
- Rationale: Run 2 uses more sophisticated tooling (70% weight vs 30%)

### 4. Authentication & Access Requirements
- Prefer Run 2 values
- Add authentication_consistency: <bool> - do both runs agree?
- Add authentication_notes: Document if runs disagreed

### 5. Data Catalog
- total_files_discovered: Use Run 2
- file_formats: Merge counts from both runs (prefer Run 2 for conflicts)
- data_categories: Unique categories from both runs
- downloadable_files: All unique files from both runs

### 6. Scraper Recommendation
- Prefer Run 2 (more informed decision)
- Merge key_challenges from both runs

### 7. Discrepancies
- Include discrepancies from BOTH runs
- Mark which run found each discrepancy

### 8. Collation Metadata (NEW SECTION)
Add collation_metadata with:
- collation_timestamp: Current timestamp
- run1_timestamp: From run1.timestamp
- run2_timestamp: From run2.timestamp
- validation_report: "datasource_analysis/ba_validation_report.json"
- runs_compared: 2
- collation_agent: "ba-collator"
- run1_endpoints_total: Count of endpoints in Run 1
- run1_endpoints_included: Count of Run 1 endpoints included in final spec (should be 0 or matches Run 2)
- run1_endpoints_excluded: Count of Run 1-only endpoints excluded
- run2_endpoints_total: Count of endpoints in Run 2
- run2_endpoints_included: Count of Run 2 endpoints included in final spec (should equal run2_endpoints_total)
- filtering_strategy: "exclude_run1_missing_in_run2"
- filtering_rationale: "Run 2 is source of truth when confidence < 0.8"

### 9. Collation Analysis (NEW SECTION)
Add collation_analysis with:
- run_comparison: {{"endpoints_run1": <count>, "endpoints_run2": <count>, ...}}
- improvements_from_run2: List of specific improvements (e.g., "Added 44 endpoints")
- discrepancies_resolved: List of conflicts and how they were resolved
- consistency_checks: Map of areas checked and consistency results

### 10. Artifacts & Next Steps
- artifacts_generated: Merge unique artifacts from both runs
- next_steps: Prefer Run 2's next steps (more complete picture)

## Conflict Resolution Rules:

Apply these 5 rules IN ORDER:

**Rule 1 - Trust Run 2 as Source of Truth:**
- Run 2's endpoint list is the ONLY source when Run 2 is required (confidence < 0.8)
- EXCLUDE Run 1 endpoints that are missing from Run 2 (likely incorrect/legacy)
- Rationale: Run 2 uses more sophisticated tooling (Botasaurus) and gets 70% weight
- Run 2 validates Run 1's findings through cross-validation

**Rule 2 - Trust Consistency:**
- If BOTH runs agree on a value → High confidence (add +0.05 bonus)
- If both agree on auth method, data format, endpoint accessibility → Keep shared value

**Rule 3 - Prefer Comprehensive Over Partial:**
- If Run 1 has incomplete data and Run 2 has complete → Use Run 2
- If Run 1 is PARTIAL and Run 2 is COMPLETE → Use Run 2

**Rule 4 - Include BOTH Values for Accessibility Claims:**
- If Run 1 says "endpoint accessible" and Run 2 says "endpoint requires auth":
  * Include BOTH in auth_claims array
  * Mark for verification
  * Add note: "Accessibility differs between runs - needs verification"

**Rule 5 - Preserve Testing Evidence for Included Endpoints:**
- For endpoints included in the final spec, preserve curl outputs from both runs
- Include test results from both passes for validation consistency
- Show what was tested in Run 1 vs Run 2 (tested_in_run1, tested_in_run2 flags)
- Testing evidence for Run 1-only endpoints is not included (endpoints are excluded)

## Output Requirements:

Return a complete ValidatedSpec that:
- Combines the best of both runs
- Documents improvements from Run 1 → Run 2
- Flags any inconsistencies or discrepancies
- Includes collation_metadata and collation_analysis sections
- Uses weighted confidence scoring throughout
- Clearly marks cross-run validation fields in endpoints

Return your merged result as JSON matching the ValidatedSpec schema."""
