#!/usr/bin/env python3
"""Quick script to run scraper generator."""
import asyncio
import sys
from pathlib import Path
from agentic_scraper.generators.orchestrator import ScraperOrchestrator

async def main():
    if len(sys.argv) < 2:
        print("Usage: python run_generator.py <url> [output_dir]")
        sys.exit(1)

    url = sys.argv[1]
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    print(f"Generating scraper for: {url}")
    print(f"Output directory: {output_dir}")

    orchestrator = ScraperOrchestrator()
    result = await orchestrator.generate_from_url(url, output_dir=output_dir)

    print(f"\n✅ Generation complete!")
    print(f"Generated {len(result.generated_files)} scraper(s)")
    for files in result.generated_files:
        print(f"  - {files.scraper_path}")

if __name__ == "__main__":
    asyncio.run(main())
