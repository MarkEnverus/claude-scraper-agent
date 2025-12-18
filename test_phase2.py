"""Test Phase 2 implementation with MISO API."""
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from claude_scraper.agents.ba_analyzer import BAAnalyzer
from claude_scraper.tools.botasaurus_tool import BotasaurusTool

async def test_phase2():
    """Test Phase 0, 1, and 2 analysis."""
    url = "https://data-exchange.misoenergy.org/api-details#api=pricing-api"

    # Initialize analyzer
    botasaurus = BotasaurusTool()
    analyzer = BAAnalyzer(botasaurus=botasaurus)

    print(f"Testing Phase 0-2 analysis for: {url}\n")

    # Phase 0: Detection
    print("=" * 60)
    print("PHASE 0: Detection")
    print("=" * 60)
    phase0 = await analyzer.analyze_phase0(url)
    print(f"✓ Detected type: {phase0.detected_type} (confidence: {phase0.confidence:.2f})")
    print(f"✓ Found {len(phase0.endpoints)} endpoints")

    # Phase 1: Documentation
    print("\n" + "=" * 60)
    print("PHASE 1: Documentation")
    print("=" * 60)
    phase1 = await analyzer.analyze_phase1(url, phase0)
    print(f"✓ Documented {len(phase1.endpoints)} endpoints")
    print(f"✓ Doc quality: {phase1.doc_quality}")
    print(f"✓ Auth required: {phase1.auth_claims.conclusion}")

    # Phase 2: Live Testing
    print("\n" + "=" * 60)
    print("PHASE 2: Live Testing")
    print("=" * 60)
    print(f"Testing {len(phase1.endpoints)} endpoints (rate limited to 1 req/sec)...")
    print("This will take approximately 10 seconds...\n")

    phase2 = await analyzer.analyze_phase2(url, phase0, phase1)
    print(f"\n✓ Phase 2 complete!")
    print(f"✓ Test results saved to: api_validation_tests/")

    print("\n" + "=" * 60)
    print("ALL PHASES COMPLETE")
    print("=" * 60)
    print(f"Phase 0: {len(phase0.endpoints)} endpoints detected")
    print(f"Phase 1: {len(phase1.endpoints)} endpoints documented")
    print(f"Phase 2: Testing complete")
    print("\nCheck datasource_analysis/ for results")

if __name__ == "__main__":
    asyncio.run(test_phase2())
