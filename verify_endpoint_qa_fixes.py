#!/usr/bin/env python3
"""Verify all Endpoint QA fixes are properly implemented."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from claude_scraper.agents.endpoint_qa import EndpointQATester


def verify_decision_matrix():
    """Verify decision matrix has all required status codes."""
    tester = EndpointQATester()
    
    required_codes = {
        # 2xx Success codes
        200: "keep", 201: "keep", 202: "keep", 203: "keep", 204: "keep", 206: "keep",
        # 3xx Redirect codes
        301: "keep", 302: "keep", 307: "keep", 308: "keep",
        # 4xx Client errors
        401: "keep", 403: "keep", 404: "remove", 405: "keep",
        # 5xx Server errors
        429: "flag", 500: "flag", 502: "flag", 503: "flag",
    }
    
    print("✓ Verifying Decision Matrix...")
    for code, expected in required_codes.items():
        actual = tester._get_decision(code)
        assert actual == expected, f"Status {code}: expected {expected}, got {actual}"
        print(f"  ✓ {code} -> {expected}")
    
    print("✓ All status codes verified!\n")


def verify_context_manager():
    """Verify context manager protocol is implemented."""
    print("✓ Verifying Context Manager...")
    
    # Check methods exist
    assert hasattr(EndpointQATester, '__enter__'), "Missing __enter__ method"
    assert hasattr(EndpointQATester, '__exit__'), "Missing __exit__ method"
    print("  ✓ __enter__ method exists")
    print("  ✓ __exit__ method exists")
    
    # Test context manager usage
    with EndpointQATester() as tester:
        assert tester is not None, "Context manager should return tester"
        assert tester.client is not None, "Client should be initialized"
    print("  ✓ Context manager works correctly")
    print("✓ Context manager verified!\n")


def verify_rate_limiting_fix():
    """Verify rate limiting timing fix."""
    print("✓ Verifying Rate Limiting Fix...")
    
    # Read source code to verify fix
    source_file = Path(__file__).parent / "claude_scraper" / "agents" / "endpoint_qa.py"
    source = source_file.read_text()
    
    # Check that last_request_time is set in test_endpoint after _enforce_rate_limit
    test_endpoint_section = source[source.find("def test_endpoint"):source.find("def _get_decision")]
    
    enforce_pos = test_endpoint_section.find("self._enforce_rate_limit()")
    timestamp_pos = test_endpoint_section.find("self.last_request_time = time.time()")
    
    assert enforce_pos > 0, "Could not find _enforce_rate_limit() call"
    assert timestamp_pos > 0, "Could not find last_request_time assignment"
    assert timestamp_pos > enforce_pos, "last_request_time should be AFTER _enforce_rate_limit()"
    
    print("  ✓ last_request_time is set AFTER rate limit check")
    print("  ✓ Timing accuracy fix verified")
    print("✓ Rate limiting fix verified!\n")


def verify_filter_endpoints_logging():
    """Verify filter_endpoints has missing endpoint handling."""
    print("✓ Verifying Filter Endpoints Enhancement...")
    
    source_file = Path(__file__).parent / "claude_scraper" / "agents" / "endpoint_qa.py"
    source = source_file.read_text()
    
    # Check for warning log in filter_endpoints
    filter_section = source[source.find("def filter_endpoints"):source.find("def filter_endpoints") + 2000]
    
    assert "logger.warning" in filter_section, "Missing warning log for missing endpoints"
    assert "decision is None" in filter_section, "Missing check for None decision"
    assert "Endpoint not found in test results" in filter_section, "Missing warning message"
    
    print("  ✓ Missing endpoint warning implemented")
    print("  ✓ Explicit None handling added")
    print("✓ Filter endpoints enhancement verified!\n")


def verify_unknown_status_logging():
    """Verify _get_decision logs unknown status codes."""
    print("✓ Verifying Unknown Status Code Logging...")
    
    source_file = Path(__file__).parent / "claude_scraper" / "agents" / "endpoint_qa.py"
    source = source_file.read_text()
    
    # Check for warning log in _get_decision
    decision_section = source[source.find("def _get_decision"):source.find("def _get_decision") + 1000]
    
    assert "logger.warning" in decision_section, "Missing warning log for unknown status codes"
    assert "Unknown HTTP status code" in decision_section, "Missing warning message"
    
    print("  ✓ Unknown status code warning implemented")
    print("✓ Unknown status code logging verified!\n")


if __name__ == "__main__":
    print("=" * 60)
    print("ENDPOINT QA FIXES VERIFICATION")
    print("=" * 60)
    print()
    
    try:
        verify_decision_matrix()
        verify_context_manager()
        verify_rate_limiting_fix()
        verify_filter_endpoints_logging()
        verify_unknown_status_logging()
        
        print("=" * 60)
        print("✓ ALL FIXES VERIFIED SUCCESSFULLY!")
        print("=" * 60)
        print()
        print("Summary:")
        print("  • Decision matrix: 18 status codes (6 added)")
        print("  • Context manager: Implemented (__enter__, __exit__)")
        print("  • Rate limiting: Timing accuracy fixed")
        print("  • Filter endpoints: Missing endpoint handling added")
        print("  • Unknown status codes: Warning logging added")
        print()
        
    except AssertionError as e:
        print(f"\n✗ VERIFICATION FAILED: {e}")
        sys.exit(1)
