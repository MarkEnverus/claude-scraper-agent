"""Simple example of using the BA Analyzer programmatically.

This shows how to use the new Python CLI implementation as a library.
"""
import asyncio
import logging

from claude_scraper.agents.ba_analyzer import BAAnalyzer
from claude_scraper.tools.botasaurus_tool import BotasaurusTool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


async def analyze_miso_api():
    """Analyze MISO Energy Pricing API."""
    url = "https://data-exchange.misoenergy.org/api-details#api=pricing-api"

    print(f"Analyzing: {url}\n")

    # Initialize the analyzer
    botasaurus = BotasaurusTool()
    analyzer = BAAnalyzer(botasaurus=botasaurus)

    # Run complete 4-phase analysis
    spec = await analyzer.run_full_analysis(url)

    # Display results
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print(f"Source: {spec.source}")
    print(f"Type: {spec.source_type}")
    print(f"Confidence: {spec.validation_summary.confidence_score:.2f}")
    print(f"Endpoints Found: {len(spec.endpoints)}")
    print(f"Auth Required: {spec.authentication.required}")
    print(f"Auth Method: {spec.authentication.method}")
    print(f"Registration URL: {spec.authentication.registration_url}")
    print(f"\nScraper Recommendation: {spec.scraper_recommendation.type}")
    print(f"Complexity: {spec.scraper_recommendation.complexity}")
    print(f"Estimated Effort: {spec.scraper_recommendation.estimated_effort}")

    # Show discrepancies if any
    if spec.discrepancies:
        print(f"\n{len(spec.discrepancies)} Discrepancies Found:")
        for disc in spec.discrepancies:
            print(f"  - {disc.type}: {disc.resolution}")

    print("\nOutput Files:")
    print("  ✓ datasource_analysis/phase0_detection.json")
    print("  ✓ datasource_analysis/phase1_documentation.json")
    print("  ✓ datasource_analysis/phase2_tests.json")
    print("  ✓ datasource_analysis/validated_datasource_spec.json")


async def analyze_by_phases():
    """Example showing phase-by-phase analysis with custom logic."""
    url = "https://api.example.com/docs"

    botasaurus = BotasaurusTool()
    analyzer = BAAnalyzer(botasaurus=botasaurus)

    # Phase 0: Detection
    print("Phase 0: Detecting data source type...")
    phase0 = await analyzer.analyze_phase0(url)
    print(f"  Detected: {phase0.detected_type} (confidence: {phase0.confidence:.2f})")

    # Custom logic based on detected type
    if phase0.detected_type == "API":
        print(f"  Found {len(phase0.endpoints)} API endpoints")

    # Phase 1: Documentation
    print("\nPhase 1: Extracting documentation...")
    phase1 = await analyzer.analyze_phase1(url, phase0)
    print(f"  Documented {len(phase1.endpoints)} endpoints")
    print(f"  Doc quality: {phase1.doc_quality}")

    # Custom logic - skip Phase 2 if no endpoints
    if len(phase1.endpoints) == 0:
        print("\nNo endpoints found - skipping Phase 2 testing")
        return

    # Phase 2: Testing
    print("\nPhase 2: Testing endpoints...")
    phase2 = await analyzer.analyze_phase2(url, phase0, phase1)
    print(f"  Auth required: {phase2.conclusion.auth_required}")

    # Phase 3: Validation
    print("\nPhase 3: Cross-checking and validation...")
    phase3 = await analyzer.analyze_phase3(url, phase0, phase1, phase2)
    print(f"  Final confidence: {phase3.validation_summary.confidence_score:.2f}")
    print(f"  Discrepancies: {len(phase3.discrepancies)}")

    return phase3


if __name__ == "__main__":
    # Run the simple analysis
    asyncio.run(analyze_miso_api())

    # Uncomment to try phase-by-phase analysis:
    # asyncio.run(analyze_by_phases())
