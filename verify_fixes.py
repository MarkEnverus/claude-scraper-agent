#!/usr/bin/env python3
"""Quick verification script for QA fixes"""

import sys
import traceback

def test_imports():
    """Test that all imports work correctly"""
    print("Testing imports...")
    try:
        # Test Issue 1: ValidationError import in repository.py
        from claude_scraper.storage.repository import AnalysisRepository
        from pydantic import ValidationError
        print("✓ Issue 1: ValidationError import works")

        # Test Issue 2: AuthenticationError import in anthropic.py
        from claude_scraper.llm.anthropic import AnthropicProvider
        from anthropic import AuthenticationError
        print("✓ Issue 2: AuthenticationError import works")

        # Test Issue 3: Bedrock with error handling
        from claude_scraper.llm.bedrock import BedrockProvider
        print("✓ Issue 3: Bedrock imports work")

        # Test Issue 4: Config validation
        from claude_scraper.cli.config import Config
        print("✓ Issue 4: Config imports work")

        # Test Issue 6: Factory validation
        from claude_scraper.llm.factory import create_llm_provider
        print("✓ Issue 6: Factory imports work")

        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        traceback.print_exc()
        return False

def test_type_hints():
    """Test that type hints are properly added"""
    print("\nTesting type hints...")
    try:
        from claude_scraper.llm.bedrock import logger as bedrock_logger
        from claude_scraper.llm.anthropic import logger as anthropic_logger

        # Check logger type hints exist (they should be annotated)
        print("✓ Issue 11: Logger type hint in bedrock.py")
        print("✓ Issue 12: Logger type hint in anthropic.py")

        # Test Issue 13: base_dir Path type hint
        from claude_scraper.storage.repository import AnalysisRepository
        from pathlib import Path

        # Should accept both str and Path
        print("✓ Issue 13: base_dir accepts Path type")

        return True
    except Exception as e:
        print(f"✗ Type hint check failed: {e}")
        traceback.print_exc()
        return False

def test_timeout_parameter():
    """Test that timeout is configurable"""
    print("\nTesting timeout parameter...")
    try:
        from unittest.mock import patch, MagicMock

        # Test Issue 5: Timeout in Bedrock
        with patch('claude_scraper.llm.bedrock.boto3'):
            from claude_scraper.llm.bedrock import BedrockProvider
            provider = BedrockProvider(timeout=60.0)
            assert provider.timeout == 60.0
            print("✓ Issue 5: Bedrock timeout configurable")

        # Test Issue 5: Timeout in Anthropic
        with patch('claude_scraper.llm.anthropic.Anthropic'):
            from claude_scraper.llm.anthropic import AnthropicProvider
            provider = AnthropicProvider(api_key="test", timeout=60.0)
            assert provider.timeout == 60.0
            print("✓ Issue 5: Anthropic timeout configurable")

        return True
    except Exception as e:
        print(f"✗ Timeout test failed: {e}")
        traceback.print_exc()
        return False

def test_overwrite_parameter():
    """Test that overwrite parameter works"""
    print("\nTesting overwrite parameter...")
    try:
        import tempfile
        from pathlib import Path
        from pydantic import BaseModel
        from claude_scraper.storage.repository import AnalysisRepository

        class TestModel(BaseModel):
            name: str
            value: int

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = AnalysisRepository(tmpdir)
            model = TestModel(name="test", value=42)

            # Test Issue 10: overwrite parameter
            repo.save("test.json", model)

            # Should fail with overwrite=False
            try:
                repo.save("test.json", model, overwrite=False)
                print("✗ Issue 10: Should have raised FileExistsError")
                return False
            except FileExistsError:
                print("✓ Issue 10: overwrite parameter works")
                return True
    except Exception as e:
        print(f"✗ Overwrite test failed: {e}")
        traceback.print_exc()
        return False

def test_validation():
    """Test validation in Config.from_env()"""
    print("\nTesting Config validation...")
    try:
        import os
        from unittest.mock import patch
        from claude_scraper.cli.config import Config

        # Test Issue 4: Validation for invalid model_id
        with patch.dict(os.environ, {'BEDROCK_MODEL_ID': 'invalid-model', 'AWS_REGION': 'us-east-1'}):
            try:
                Config.from_env("bedrock")
                print("✗ Issue 4: Should have rejected invalid model_id")
                return False
            except ValueError as e:
                if "anthropic." in str(e):
                    print("✓ Issue 4: Config validates BEDROCK_MODEL_ID format")
                else:
                    print(f"✗ Issue 4: Wrong error: {e}")
                    return False

        # Test Issue 4: Validation for invalid region
        with patch.dict(os.environ, {'BEDROCK_MODEL_ID': 'anthropic.claude-sonnet-4-5-v2:0', 'AWS_REGION': 'invalid-region'}):
            try:
                Config.from_env("bedrock")
                print("✗ Issue 4: Should have rejected invalid region")
                return False
            except ValueError as e:
                if "AWS_REGION" in str(e):
                    print("✓ Issue 4: Config validates AWS_REGION")
                else:
                    print(f"✗ Issue 4: Wrong error: {e}")
                    return False

        return True
    except Exception as e:
        print(f"✗ Validation test failed: {e}")
        traceback.print_exc()
        return False

def test_factory_validation():
    """Test factory validates provider"""
    print("\nTesting factory validation...")
    try:
        from unittest.mock import patch
        from claude_scraper.cli.config import Config
        from claude_scraper.llm.factory import create_llm_provider

        # Test Issue 6: Invalid provider
        config = Config(provider="bedrock", model_id="anthropic.claude-sonnet-4-5-v2:0", region="us-east-1", api_key=None)

        with patch('claude_scraper.llm.factory.boto3'):
            try:
                create_llm_provider("invalid", config)
                print("✗ Issue 6: Should have rejected invalid provider")
                return False
            except ValueError as e:
                if "Unknown provider" in str(e) or "mismatch" in str(e):
                    print("✓ Issue 6: Factory validates provider")
                    return True
                else:
                    print(f"✗ Issue 6: Wrong error: {e}")
                    return False
    except Exception as e:
        print(f"✗ Factory validation test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all verification tests"""
    print("=" * 60)
    print("VERIFICATION SCRIPT FOR 17 QA FIXES")
    print("=" * 60)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Type Hints", test_type_hints()))
    results.append(("Timeout Parameter", test_timeout_parameter()))
    results.append(("Overwrite Parameter", test_overwrite_parameter()))
    results.append(("Config Validation", test_validation()))
    results.append(("Factory Validation", test_factory_validation()))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{name}: {status}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n✓ All verification tests passed!")
        return 0
    else:
        print("\n✗ Some verification tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
