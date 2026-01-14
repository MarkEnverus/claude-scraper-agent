"""Utilities for working with captured network events.

Network capture is stored as a list of dicts (events). Many parts of the BA
pipeline still need URL lists (e.g., prompt rendering, OpenAPI discovery).
"""

from __future__ import annotations

from typing import Any, Dict, List


def urls_from_network_events(network_events: List[Dict[str, Any]] | None) -> List[str]:
    """Extract and deduplicate URLs from network events.

    Args:
        network_events: List of event dicts with a `url` key.

    Returns:
        Deduplicated URLs in first-seen order.
    """
    if not network_events:
        return []

    urls: List[str] = []
    seen = set()
    for event in network_events:
        if not isinstance(event, dict):
            continue
        url = event.get("url")
        if not url or not isinstance(url, str):
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls

