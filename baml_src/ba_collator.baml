// BAML Functions for BA Collator Agent
// Merges Run 1 and Run 2 analysis results with weighted confidence scoring

// ============================================================================
// Phase 0 Collation: Merge Detection Results
// ============================================================================

function MergePhase0(
    run1: Phase0Detection,
    run2: Phase0Detection,
    run2_focus_areas: string[]
) -> Phase0Detection {
    client ClaudeBedrock
    prompt #"
        You are merging two Phase 0 data source detection analysis runs.

        ## Run 1 Result (30% weight - initial discovery):
        {{ _.role("user") }}
        {{ run1 }}

        ## Run 2 Result (70% weight - focused re-analysis):
        {{ _.role("user") }}
        {{ run2 }}

        ## Run 2 Focus Areas:
        {{ _.role("user") }}
        {{ run2_focus_areas }}

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
        - endpoints: Merged endpoints (Run 2 preferred for conflicts)
        - url: The data source URL
        - fallback_strategy: From Run 2 if available

        {{ ctx.output_format }}
    "#
}

// ============================================================================
// Complete Spec Collation: Merge Validated Specifications
// ============================================================================

function MergeCompleteSpecs(
    run1: ValidatedSpec,
    run2: ValidatedSpec
) -> ValidatedSpec {
    client ClaudeBedrock
    prompt #"
        You are merging two complete Business Analyst analysis runs into a final,
        definitive data source specification.

        ## Run 1 Specification (30% weight - initial analysis):
        {{ _.role("user") }}
        {{ run1 }}

        ## Run 2 Specification (70% weight - validator-guided focused analysis):
        {{ _.role("user") }}
        {{ run2 }}

        ## Your Task: Create the Final Merged Specification

        Apply these weighted merge rules for each section:

        ### 1. Executive Summary
        - total_endpoints_discovered: Use Run 2 (should be most complete)
        - accessible_endpoints: Use Run 2
        - success_rate: Use Run 2
        - primary_formats: Merge unique formats from both runs
        - authentication_required: If runs disagree, prefer Run 2
        - estimated_scraper_complexity: Use Run 2
        - **NEW**: Add improvements_from_run1 field documenting what Run 2 improved

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
          1. Add to final list with tested_in_run1=true, tested_in_run2=false
          2. Add note: "Found in Run 1 only - verify existence in next iteration"

        Endpoint Merging Process:
        - Start with ALL endpoints from Run 2 (most comprehensive enumeration)
        - For each Run 2 endpoint, check if it exists in Run 1:
          - If yes: Mark tested_in_run1=true, tested_in_run2=true,
            validation_consistency=<true if status matches>
          - If no: Mark tested_in_run1=false, tested_in_run2=true,
            validation_consistency="new_in_run2"
        - For any Run 1 endpoints NOT in Run 2 (shouldn't happen):
          - Add with validation_consistency="missing_in_run2"
          - Add warning note

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

        ### 9. Collation Analysis (NEW SECTION)
        Add collation_analysis with:
        - run_comparison: {"endpoints_run1": <count>, "endpoints_run2": <count>, ...}
        - improvements_from_run2: List of specific improvements (e.g., "Added 44 endpoints")
        - discrepancies_resolved: List of conflicts and how they were resolved
        - consistency_checks: Map of areas checked and consistency results

        ### 10. Artifacts & Next Steps
        - artifacts_generated: Merge unique artifacts from both runs
        - next_steps: Prefer Run 2's next steps (more complete picture)

        ## Conflict Resolution Rules:

        Apply these 5 rules IN ORDER:

        **Rule 1 - Trust Run 2 for Enumeration:**
        - Run 2's endpoint list is the PRIMARY source (validator-guided focused analysis)
        - BUT preserve Run 1 endpoints with warning note if missing from Run 2
        - Example: If Run 1 has endpoint X but Run 2 doesn't, include it with note: "Found in Run 1 only - verify in next iteration"

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

        **Rule 5 - Merge Testing Evidence:**
        - ALWAYS preserve curl outputs from both runs
        - Include test results from both passes
        - Show what was tested in Run 1 vs Run 2

        NEVER discard endpoints or testing evidence without investigation.

        ## Output Requirements:

        Return a complete ValidatedSpec that:
        - Combines the best of both runs
        - Documents improvements from Run 1 → Run 2
        - Flags any inconsistencies or discrepancies
        - Includes collation_metadata and collation_analysis sections
        - Uses weighted confidence scoring throughout
        - Clearly marks cross-run validation fields in endpoints

        {{ ctx.output_format }}
    "#
}
