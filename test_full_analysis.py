"""Test complete 4-phase analysis with MISO API."""
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from claude_scraper.agents.ba_analyzer import BAAnalyzer
from claude_scraper.tools.botasaurus_tool import BotasaurusTool

async def test_full_analysis():
    """Test complete 4-phase analysis."""
    url = "https://data-exchange.misoenergy.org/api-details#api=pricing-api"

    # Initialize analyzer
    botasaurus = BotasaurusTool()
    analyzer = BAAnalyzer(botasaurus=botasaurus)

    print(f"\n{'='*70}")
    print(f"FULL 4-PHASE ANALYSIS")
    print(f"{'='*70}")
    print(f"URL: {url}\n")

    # Run full analysis
    print("Starting complete analysis pipeline...")
    print("This will take approximately 15-20 seconds...\n")

    try:
        validated_spec = await analyzer.run_full_analysis(url)

        print(f"\n{'='*70}")
        print("✓ ANALYSIS COMPLETE!")
        print(f"{'='*70}\n")

        print(f"Source Type: {validated_spec.source_type}")
        print(f"Confidence Score: {validated_spec.validation_summary.confidence_score:.2f}")
        print(f"Endpoints Validated: {len(validated_spec.endpoints)}")
        print(f"Discrepancies Found: {len(validated_spec.discrepancies)}")
        print(f"Scraper Type Recommended: {validated_spec.scraper_recommendation.type}")

        print(f"\n{'='*70}")
        print("OUTPUT FILES")
        print(f"{'='*70}")
        print("✓ datasource_analysis/phase0_detection.json")
        print("✓ datasource_analysis/phase1_documentation.json")
        print("✓ datasource_analysis/phase2_tests.json")
        print("✓ datasource_analysis/validated_datasource_spec.json")
        print("✓ api_validation_tests/test_*.txt (10 files)")

        if validated_spec.discrepancies:
            print(f"\n{'='*70}")
            print("DISCREPANCIES FOUND")
            print(f"{'='*70}")
            for idx, disc in enumerate(validated_spec.discrepancies, 1):
                print(f"\n{idx}. {disc.field}")
                print(f"   Phase 1: {disc.phase1_value}")
                print(f"   Phase 2: {disc.phase2_value}")
                print(f"   Resolution: {disc.resolution}")

        print(f"\n{'='*70}")
        print("SCRAPER RECOMMENDATION")
        print(f"{'='*70}")
        print(f"Type: {validated_spec.scraper_recommendation.type}")
        print(f"Reasoning: {validated_spec.scraper_recommendation.reasoning}")

        print(f"\n✓ Full 4-phase analysis completed successfully!\n")

    except Exception as e:
        print(f"\n✗ Analysis failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_full_analysis())
