"""ReAct Planner Node for LangGraph BA Analyst.

This module implements the planning node using LangChain's ReAct pattern with
tool binding. The LLM makes decisions about which tools to use and when, replacing
deterministic heuristics with agentic reasoning.

Following langchain-experimental pattern:
- Uses create_agent() from langchain.agents
- Tools: render_page_with_js, http_get_headers, extract_links
- MemorySaver for conversation state
- SystemMessage for agent instructions
"""

from typing import Dict, Any, Optional
import logging
from urllib.parse import urlparse, urlunparse, parse_qs
from langchain.agents import create_agent
from langchain.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from agentic_scraper.business_analyst.state import BAAnalystState
from agentic_scraper.business_analyst.config import BAConfig
from agentic_scraper.llm.factory import LLMFactory
from agentic_scraper.business_analyst.tools import (
    render_page_with_js,
    http_get_headers,
    http_get_robots,
    extract_links,
)
from agentic_scraper.business_analyst.utils.link_scoring import (
    is_junk_link,
    score_link_deterministic,
)
from agentic_scraper.business_analyst.utils.api_call_extractor import (
    extract_api_calls_from_network_events,
    prioritize_apim_calls,
)

logger = logging.getLogger(__name__)


def score_url_priority(
    url: str,
    seed_url: str,
    primary_api_name: Optional[str]
) -> float:
    """Score URL relevance for queue prioritization. Higher = visit sooner.

    Priority levels:
    10.0+ = Seed URL subdirectories (e.g., /api-details/operations)
    5.0+  = Contains primary_api_name in URL or path
    3.0+  = API-specific pages (operation details, examples, schemas)
    1.0+  = General catalog/overview pages (/apis, /browse)
    -5.0  = Other specific APIs (different #api= fragment)

    This ensures deep exploration of seed URL content before wandering
    to catalog pages or other APIs.

    Args:
        url: URL to score
        seed_url: Seed URL from initial state
        primary_api_name: Primary API name extracted from seed URL fragment

    Returns:
        Priority score (higher = visit sooner)

    Example:
        >>> seed = "https://data-exchange.misoenergy.org/api-details#api=pricing-api"
        >>> score_url_priority(
        ...     "https://data-exchange.misoenergy.org/api-details/operations",
        ...     seed,
        ...     "pricing-api"
        ... )
        15.0  # 10.0 (subdirectory) + 5.0 (contains "pricing-api")
        >>> score_url_priority(
        ...     "https://data-exchange.misoenergy.org/apis",
        ...     seed,
        ...     "pricing-api"
        ... )
        1.0  # Just catalog keyword
    """
    from urllib.parse import urlparse

    score = 0.0
    parsed_url = urlparse(url)
    parsed_seed = urlparse(seed_url)
    seed_base = f"{parsed_seed.scheme}://{parsed_seed.netloc}{parsed_seed.path}"

    # 1. Seed URL subdirectory = HIGHEST priority
    # Example: seed=/api-details#api=pricing-api, url=/api-details/operations
    if url.startswith(seed_base.split('#')[0]):
        score += 10.0

    # 2. Contains primary API name = HIGH priority
    if primary_api_name and primary_api_name.lower() in url.lower():
        score += 5.0

    # 3. API-specific keywords = MEDIUM priority
    api_keywords = ['operation', 'endpoint', 'example', 'schema', 'doc', 'reference']
    if any(keyword in url.lower() for keyword in api_keywords):
        score += 3.0

    # 4. General catalog/overview = LOW priority (visit AFTER seed)
    catalog_keywords = ['/apis', '/api-catalog', '/browse', '/list']
    if any(keyword in url.lower() for keyword in catalog_keywords):
        score += 1.0

    # 5. Other specific APIs = VERY LOW (penalize)
    # Example: url has #api=load-generation when primary_api_name=pricing-api
    if '#api=' in url and primary_api_name and primary_api_name not in url:
        score -= 5.0

    return score


# Cache for robots.txt to avoid repeated fetches
_robots_cache: dict[str, dict] = {}


def get_robots_disallowed_paths(seed_url: str) -> list[str]:
    """Fetch and cache disallowed paths from robots.txt.

    Args:
        seed_url: Any URL from the domain to fetch robots.txt for

    Returns:
        List of disallowed path patterns (e.g., ['/admin/', '/private/'])
    """
    parsed = urlparse(seed_url)
    domain = f"{parsed.scheme}://{parsed.netloc}"

    if domain in _robots_cache:
        return _robots_cache[domain].get('disallowed_paths', [])

    try:
        result = http_get_robots.invoke(seed_url)
        _robots_cache[domain] = result
        logger.info(f"Fetched robots.txt for {domain}: {len(result.get('disallowed_paths', []))} disallowed paths")
        return result.get('disallowed_paths', [])
    except Exception as e:
        logger.warning(f"Failed to fetch robots.txt for {domain}: {e}")
        _robots_cache[domain] = {'disallowed_paths': [], 'error': str(e)}
        return []


def is_robots_disallowed(url: str, disallowed_paths: list[str]) -> bool:
    """Check if URL matches any disallowed robots.txt pattern (E5).

    Args:
        url: URL to check
        disallowed_paths: List of disallowed path patterns from robots.txt

    Returns:
        True if URL is disallowed, False otherwise
    """
    if not disallowed_paths:
        return False

    parsed = urlparse(url)
    path = parsed.path

    for disallowed in disallowed_paths:
        # Handle wildcard patterns (basic support)
        if disallowed.endswith('*'):
            if path.startswith(disallowed[:-1]):
                return True
        elif path.startswith(disallowed):
            return True

    return False


def trim_message_history(messages: list, max_messages: int = 12) -> list:
    """Keep only the most recent messages to prevent context overflow.

    Args:
        messages: Full message history from MemorySaver
        max_messages: Maximum messages to keep (default: 12 = ~2-3 analysis cycles)

    Returns:
        Trimmed message list with most recent messages
    """
    if len(messages) <= max_messages:
        return messages

    # Keep system message (first) + recent messages
    system_msg = messages[0] if messages and hasattr(messages[0], 'type') and messages[0].type == 'system' else None
    recent_messages = messages[-max_messages:]

    if system_msg and system_msg not in recent_messages:
        return [system_msg] + recent_messages
    return recent_messages


def url_key(url: str) -> str:
    """Canonical form for URL comparison.

    Rules:
    - Lowercase scheme + netloc only (NOT path/query - server-dependent)
    - Strip trailing / from path
    - Preserve fragment if it looks like a meaningful route:
      - Starts with / (SPA route: #/foo)
      - Starts with !/ (hashbang route: #!/foo)
      - Contains api= parameter (state parameter: #api=pricing-api)
    - Drop fragment only for inert anchors (#section-2)

    Examples:
        https://Data-Exchange.MISOEnergy.org/api-details#api=pricing-api
          → https://data-exchange.misoenergy.org/api-details#api=pricing-api

        https://portal.spp.org/groups/integrated-marketplace#/dashboard
          → https://portal.spp.org/groups/integrated-marketplace#/dashboard

        https://portal.spp.org/groups/integrated-marketplace/
          → https://portal.spp.org/groups/integrated-marketplace

        https://example.com/page#section-2
          → https://example.com/page
    """
    parsed = urlparse(url)

    # Lowercase scheme + netloc only
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip('/')

    # Preserve fragment if it looks like a meaningful route
    fragment = parsed.fragment
    if fragment:
        # Check if fragment looks like a route
        is_spa_route = fragment.startswith('/') or fragment.startswith('!/')

        # Check if fragment contains api= parameter
        frag_params = parse_qs(fragment)
        has_api_param = 'api' in frag_params

        # Keep fragment only if it's a route or has meaningful params
        if not (is_spa_route or has_api_param):
            fragment = ''  # Drop inert anchors like #section-2

    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, fragment))


# ============================================================================
# Agent Creation
# ============================================================================

def create_planner_react_agent(config: BAConfig):
    """Create ReAct planner agent with tool access.

    This follows the langchain-experimental pattern:
    - Uses ChatBedrockConverse with reasoning
    - create_agent() for tool binding (not create_react_agent)
    - SystemMessage for agent behavior
    - MemorySaver for state management

    Args:
        config: BAConfig with LLM settings

    Returns:
        Compiled agent ready to invoke with tools

    Example:
        >>> config = BAConfig()
        >>> agent = create_planner_react_agent(config)
        >>> result = agent.invoke({"messages": [HumanMessage(content="...")]})
    """
    # Create fast model for planner (Haiku, no extended thinking)
    factory = LLMFactory(config=config, region=config.aws_region)
    llm = factory.create_fast_model()
    logger.info("Created fast model for planner_react agent (Haiku, cost-effective)")

    # System prompt for planner behavior
    system_prompt = SystemMessage(content="""You are a planning agent for web scraping and API discovery.

Your goal: Analyze websites to discover API endpoints, documentation, and data sources.

Available tools:
- render_page_with_js: Use for JavaScript-heavy pages (SPAs, React apps, portals)
  - Renders JS, expands sections, captures network calls, takes screenshots
  - Use when: "portal" in domain, empty pages, 0 links found, dynamic content expected
- http_get_headers: Quick check of HTTP status and headers
  - Fast metadata check without fetching body
  - Use when: checking auth (401/403), status codes, content types
- extract_links: Extract all links from a page
  - Faster than render_page_with_js when you only need links
  - Use when: following navigation, building site map

Decision-making strategy:
1. For URLs with "portal", "app", or "dashboard" in domain → use render_page_with_js
2. For empty pages or 0 links returned → use render_page_with_js
3. Use http_get_headers to check status before deciding tool choice
4. Prioritize links with "api", "docs", "endpoint", "data" keywords
5. Stop when sufficient endpoints found or no high-value links remain

Always reason step-by-step about which tool to use and why.
Think about: What information do I need? Which tool gives me that information most efficiently?
""")

    # Create agent with tools (following langchain-experimental pattern)
    agent = create_agent(
        model=llm,
        tools=[render_page_with_js, http_get_headers, extract_links],
        system_prompt=system_prompt,
        checkpointer=MemorySaver(),
    )

    logger.info("ReAct agent created with 3 tools: render_page_with_js, http_get_headers, extract_links")
    return agent


# ============================================================================
# Helper Functions
# ============================================================================

def format_recent_findings(state: BAAnalystState) -> str:
    """Format recent findings for context message."""
    recent_endpoints = state["endpoints"][-3:] if state["endpoints"] else []
    if not recent_endpoints:
        return "- No endpoints discovered yet"

    lines = []
    for ep in recent_endpoints:
        lines.append(f"- {ep.name}: {ep.url} ({ep.method_guess})")
    return "\n".join(lines)


def format_queue_links(state: BAAnalystState, limit: int = 5) -> str:
    """Format top links in queue for context message.

    CRITICAL: Filter out URLs that completed analyst AI analysis to prevent loops.

    Conservative filtering approach:
    - "visited" = URLs we attempted to fetch
    - "artifacts" = URLs we successfully rendered with browser
    - "analyzed_urls" = URLs we sent to analyst AI (WHAT WE FILTER ON)
    """
    # Filter queue: exclude URLs that completed analyst AI analysis
    analyzed_urls = state.get("analyzed_urls", set())
    filtered_queue = [
        link for link in state["queue"]
        if link.get("url") not in analyzed_urls  # Only filter URLs sent to AI
    ]

    top_links = filtered_queue[:limit]
    if not top_links:
        return "- Queue is empty (all links analyzed or filtered)"

    lines = []
    for i, link in enumerate(top_links, 1):
        url = link.get("url", "unknown")
        score = link.get("combined_score", 0.0)
        reason = link.get("reason", "")
        lines.append(f"{i}. [Score: {score:.2f}] {url}\n   Reason: {reason}")

    logger.debug(f"Filtered queue: {len(state['queue'])} → {len(filtered_queue)} (removed {len(state['queue']) - len(filtered_queue)} analyzed)")
    return "\n".join(lines)


def format_analyzed_urls(state: BAAnalystState, limit: int = 10) -> str:
    """Format already analyzed URLs with warning.

    This section informs the agent which URLs have already been analyzed
    and should NOT be revisited. Tools will block attempts to re-analyze these.
    """
    analyzed_urls = state.get("analyzed_urls", set())
    if not analyzed_urls:
        return ""

    url_list = list(analyzed_urls)[:limit]
    formatted = "\n".join(f"  ✓ {url}" for url in url_list)

    return f"""
⚠️ ALREADY ANALYZED (DO NOT REVISIT):
{formatted}

CRITICAL: These URLs were sent to the analyst. Tools will block attempts to revisit them.
Use ONLY URLs from the "Top links in queue" section below.
"""


def extract_artifacts_from_messages(messages: list, state: BAAnalystState) -> Dict[str, Any]:
    """Extract PageArtifacts from tool results in agent messages.

    The agent calls tools like render_page_with_js which return data.
    We need to convert those tool results into PageArtifact objects
    and store them in state.

    Args:
        messages: List of messages from agent.invoke()
        state: Current state (to update artifacts)

    Returns:
        Dictionary with:
        - artifacts: Dict[url, PageArtifact]
        - screenshots: Dict[url, screenshot_path]
        - visited: Set of URLs that were fetched

    Example:
        >>> messages = agent.invoke({"messages": [...]})["messages"]
        >>> artifacts = extract_artifacts_from_messages(messages, state)
    """
    from agentic_scraper.business_analyst.state import PageArtifact, LinkInfo, AuthSignals

    artifacts = {}
    screenshots = {}
    visited = set()
    candidate_api_calls = []

    # Build map of tool_call_id -> URL from AIMessage tool calls
    tool_call_urls = {}
    logger.info(f"Processing {len(messages)} messages to extract artifacts")

    for i, msg in enumerate(messages):
        logger.debug(f"Message {i}: type={getattr(msg, 'type', 'unknown')}, class={msg.__class__.__name__}")

        if hasattr(msg, 'type') and msg.type == 'ai':
            # Check for tool_calls in the message
            if hasattr(msg, 'tool_calls'):
                logger.info(f"Found AI message with {len(msg.tool_calls)} tool_calls")
                for tool_call in msg.tool_calls:
                    logger.debug(f"Tool call type: {type(tool_call)}, content: {tool_call}")

                    # Handle both dict and object access
                    if isinstance(tool_call, dict):
                        tool_call_id = tool_call.get('id')
                        args = tool_call.get('args', {})
                    else:
                        tool_call_id = getattr(tool_call, 'id', None)
                        args = getattr(tool_call, 'args', {})

                    if args and 'url' in args:
                        tool_call_urls[tool_call_id] = args['url']
                        logger.info(f"Mapped tool_call {tool_call_id} to URL: {args['url']}")

    # Look for ToolMessage responses
    for msg in messages:
        if hasattr(msg, 'type') and msg.type == 'tool':
            # This is a tool response
            tool_name = getattr(msg, 'name', 'unknown')
            tool_call_id = getattr(msg, 'tool_call_id', None)
            content = getattr(msg, 'content', {})

            logger.info(f"Found ToolMessage: name={tool_name}, tool_call_id={tool_call_id}")
            logger.debug(f"Content type: {type(content)}, is_dict: {isinstance(content, dict)}")
            if isinstance(content, dict):
                logger.debug(f"Content keys: {list(content.keys())}")
            else:
                logger.debug(f"Content value: {content[:200] if content else 'empty'}")

            # CRITICAL: Check if this is a blocked tool result - skip it
            if isinstance(content, dict) and content.get("blocked"):
                logger.debug(f"Skipping blocked tool result for URL: {content.get('url')}")
                continue  # Do not create artifact/visited for blocked

            # Get URL from tool call mapping
            url = tool_call_urls.get(tool_call_id, 'unknown')

            logger.info(f"Processing tool result: {tool_name} for URL: {url}")

            # Parse JSON string content if needed
            if isinstance(content, str):
                try:
                    import json
                    content = json.loads(content)
                    logger.info(f"Parsed JSON string content to dict")
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse content as JSON: {e}")
                    # Keep as string

            # Handle render_page_with_js results
            if tool_name == 'render_page_with_js' and isinstance(content, dict):
                if url == 'unknown':
                    logger.warning("Could not determine URL for render_page_with_js result")
                    continue

                # Create PageArtifact from tool result
                artifact = PageArtifact(
                    url=url,
                    status_code=200,  # Tool succeeded
                    headers={},
                    html_excerpt=content.get('full_text', '')[:5000],
                    markdown_excerpt=content.get('markdown', '')[:5000],
                    screenshot_path=content.get('screenshot'),
                    links=[],  # Will be populated from navigation_links
                    auth_signals=AuthSignals(),  # Will be analyzed later
                    network_events=content.get('network_events', [])
                )

                # Convert navigation_links to LinkInfo with scoring
                seed_url = state.get("seed_url", "")
                visited = state.get("visited", set())
                junk_filtered = 0

                for link in content.get('navigation_links', [])[:50]:  # Limit to 50
                    link_url = link.get('href', '')
                    link_text = link.get('text', '')

                    if not link_url:
                        continue

                    # Apply junk filter first (hard filter)
                    is_junk, junk_reason = is_junk_link(link_url, link_text)
                    if is_junk:
                        junk_filtered += 1
                        logger.debug(f"Filtered junk link: {link_url[:60]}... ({junk_reason})")
                        continue

                    # Score the link using deterministic heuristics
                    score, reason = score_link_deterministic(link_url, link_text, seed_url, visited)

                    # Add link with computed score
                    artifact.links.append(LinkInfo(
                        url=link_url,
                        text=link_text,
                        heuristic_score=score,
                        reason=reason
                    ))

                logger.info(f"Link scoring complete: {len(artifact.links)} scored, {junk_filtered} junk filtered")

                api_calls = []
                # Extract API call URLs from network events
                if artifact.network_events:
                    api_calls = extract_api_calls_from_network_events(artifact.network_events, seed_url)
                    if api_calls:
                        # Prioritize APIM calls (MISO, etc.)
                        api_calls = prioritize_apim_calls(api_calls)
                        candidate_api_calls.extend(api_calls)
                        logger.info(f"Extracted {len(api_calls)} candidate API calls from network traffic")

                artifacts[url] = artifact
                visited.add(url)

                if content.get('screenshot'):
                    screenshots[url] = content['screenshot']

                logger.info(
                    f"Created artifact for {url}: {len(artifact.links)} links, "
                    f"{len(api_calls)} API calls, screenshot={bool(artifact.screenshot_path)}"
                )

            # Handle http_get_headers results
            elif tool_name == 'http_get_headers' and isinstance(content, dict):
                if url == 'unknown':
                    logger.warning("Could not determine URL for http_get_headers result")
                    continue

                # Create minimal artifact from headers check
                artifact = PageArtifact(
                    url=url,
                    status_code=content.get('status_code', 0),
                    headers=content.get('headers', {}),
                    html_excerpt="",
                    markdown_excerpt="",
                    screenshot_path=None,
                    links=[],
                    auth_signals=AuthSignals(
                        has_401=(content.get('status_code') == 401),
                        has_403=(content.get('status_code') == 403),
                        requires_auth_header='www-authenticate' in content.get('headers', {})
                    ),
                    network_events=[]
                )

                artifacts[url] = artifact
                # Don't add to visited - this was just a header check

                logger.info(f"Created header artifact for {url}: status={artifact.status_code}")

    return {
        "artifacts": artifacts,
        "screenshots": screenshots,
        "visited": visited,
        "candidate_api_calls": candidate_api_calls
    }


def parse_agent_decision(messages: list, state: BAAnalystState) -> Dict[str, Any]:
    """Parse agent decision from message chain.

    The agent returns a list of messages including:
    - HumanMessage: Our context prompt
    - AIMessage: Agent reasoning
    - ToolMessage: Tool results
    - AIMessage: Final decision

    We need to extract:
    1. What tools were called (for artifact extraction)
    2. What the agent decided to do next

    Args:
        messages: List of messages from agent.invoke()
        state: Current state (for context)

    Returns:
        Dictionary with:
        - action: "analyze_page", "continue", or "stop"
        - url: URL that was analyzed (if applicable)
        - reason: Explanation

    Example:
        >>> messages = agent.invoke({"messages": [...]})["messages"]
        >>> decision = parse_agent_decision(messages, state)
        >>> print(decision["action"])  # "analyze_page"
    """
    # Check if agent called any tools
    tool_calls_made = any(
        hasattr(msg, 'type') and msg.type == 'tool'
        for msg in messages
    )

    # PASS 1: Build mapping of tool_call_id -> URL from AIMessage tool_calls
    tool_call_urls = {}
    for msg in messages:
        if hasattr(msg, 'type') and msg.type == 'ai':
            if hasattr(msg, 'tool_calls'):
                for tool_call in msg.tool_calls:
                    # Handle both dict and object access
                    if isinstance(tool_call, dict):
                        tool_call_id = tool_call.get('id')
                        args = tool_call.get('args', {})
                    else:
                        tool_call_id = getattr(tool_call, 'id', None)
                        args = getattr(tool_call, 'args', {})

                    if tool_call_id and args and 'url' in args:
                        tool_call_urls[tool_call_id] = args['url']
                        logger.info(f"Mapped tool_call {tool_call_id} to URL: {args['url']}")

    # PASS 2: Find render_page_with_js ToolMessage and check if blocked
    rendered_url = None
    render_blocked = False
    for msg in messages:
        if hasattr(msg, 'type') and msg.type == 'tool':
            if getattr(msg, 'name', '') == 'render_page_with_js':
                # Check if this was a blocked render
                content = getattr(msg, 'content', {})
                if isinstance(content, dict) and content.get("blocked"):
                    render_blocked = True
                    blocked_url = content.get("url")
                    blocked_reason = content.get("reason", "unknown")
                    logger.info(f"Agent attempted blocked URL: {blocked_url} (reason: {blocked_reason})")
                    break  # Found blocked render, stop processing

                # Not blocked, get URL from mapping
                tool_call_id = getattr(msg, 'tool_call_id', None)
                rendered_url = tool_call_urls.get(tool_call_id)
                if rendered_url:
                    logger.info(f"Agent called render_page_with_js on {rendered_url}")
                    break  # Found it, stop processing
                else:
                    logger.warning(f"Found render_page_with_js call but could not map tool_call_id={tool_call_id} to URL")

    # Look for final AI message to understand decision
    final_ai_message = None
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'ai':
            final_ai_message = msg
            break

    # CRITICAL: If render was blocked, return continue (never analyze_page)
    if render_blocked:
        logger.info("Agent attempted blocked URL, returning continue action")
        return {
            "action": "continue",
            "url": None,
            "reason": f"Blocked render ({blocked_reason}), moving to next URL"
        }

    # If agent rendered a page, check if it needs analysis
    if rendered_url:
        # Check if URL was already analyzed by AI
        analyzed_urls = state.get("analyzed_urls", set())
        if rendered_url in analyzed_urls:
            logger.warning(f"Agent tried to re-analyze URL that completed AI analysis: {rendered_url}")
            logger.info("Returning 'continue' to move to next URL instead")
            return {
                "action": "continue",
                "url": None,
                "reason": f"URL {rendered_url} already analyzed by AI, moving to next in queue"
            }

        # URL not analyzed yet, proceed
        return {
            "action": "analyze_page",
            "url": rendered_url,
            "reason": "Agent fetched page content, ready for deep analysis"
        }

    # If agent called tools but didn't render, it's exploring
    if tool_calls_made:
        return {
            "action": "continue",
            "url": None,
            "reason": "Agent is exploring, continue planning"
        }

    # If no tools called, check if agent wants to stop
    if final_ai_message:
        content = getattr(final_ai_message, 'content', '').lower()
        if any(word in content for word in ['stop', 'done', 'complete', 'finish', 'no more']):
            return {
                "action": "stop",
                "url": None,
                "reason": "Agent decided to stop exploration"
            }

    # Check queue - filter out analyzed URLs first (conservative check)
    analyzed_urls = state.get("analyzed_urls", set())
    unanalyzed_queue = [
        link for link in state.get("queue", [])
        if link.get("url") not in analyzed_urls  # Conservative: only filter URLs sent to AI
    ]

    if not unanalyzed_queue:
        return {
            "action": "stop",
            "url": None,
            "reason": "No unanalyzed links remaining in queue"
        }

    # Default: continue exploring
    return {
        "action": "continue",
        "url": None,
        "reason": "Continue exploration"
    }


# ============================================================================
# Planner ReAct Node
# ============================================================================

def planner_react_node(state: BAAnalystState) -> Dict[str, Any]:
    """ReAct planner node - uses agent with tools.

    This replaces the old planner_node that used deterministic heuristics.
    Now the LLM reasons about which tools to use and when.

    The agent has access to:
    - render_page_with_js: Full browser automation for JS pages
    - http_get_headers: Quick HTTP status/header checks
    - extract_links: Link extraction

    The LLM decides which tool to use based on the current state and goals.

    Args:
        state: Current LangGraph state (BAAnalystState)

    Returns:
        Dictionary with state updates:
        - next_action: "fetch_main", "follow_link", or "stop"
        - current_url: Next URL to visit (if follow_link)
        - stop_reason: Optional explanation if stopping
        - planner_agent: Agent instance (stored for reuse)

    Example:
        >>> state = {...}  # BAAnalystState
        >>> updates = planner_react_node(state)
        >>> print(updates["next_action"])  # "follow_link"
    """
    logger.info(
        "Planner ReAct node invoked: seed_url=%s, depth=%d, visited=%d, queue=%d, endpoints=%d",
        state["seed_url"],
        state["current_depth"],
        len(state["visited"]),
        len(state["queue"]),
        len(state["endpoints"])
    )

    # CRITICAL: Enforce seed URL analysis FIRST before any navigation
    # This ensures we extract ALL content from the seed page before wandering
    # NOTE: We don't bypass the agent - we just add the seed URL to the queue with high priority
    # The agent will see it's the first URL to visit and will use tools to fetch it
    seed_url = state["seed_url"]
    visited = state["visited"]
    artifacts = state.get("artifacts", {})

    # If seed URL not visited AND not in artifacts, add it to queue with max priority
    if seed_url not in visited and seed_url not in artifacts:
        logger.info("SEED URL NOT YET VISITED - Adding to queue with max priority: %s", seed_url)
        # Prepend seed URL to queue with max score
        queue = state.get("queue", [])
        seed_item = {"url": seed_url, "score": 1.0, "reason": "Seed URL - analyze first"}
        queue = [seed_item] + queue
        state = {**state, "queue": queue}

    # CRITICAL: Sort queue by priority score BEFORE agent sees it
    # This ensures deep exploration of seed URL and related pages before wandering
    primary_api_name = state.get("primary_api_name")
    queue = state.get("queue", [])

    if primary_api_name and queue:
        logger.info(f"Applying priority scoring for primary_api_name: {primary_api_name}")

        # Score each URL in queue
        scored_queue = []
        for item in queue:
            url = item["url"]
            priority_score = score_url_priority(url, seed_url, primary_api_name)
            item["priority_score"] = priority_score
            scored_queue.append(item)

        # Sort by priority_score descending (highest first)
        queue = sorted(scored_queue, key=lambda x: x.get("priority_score", 0.0), reverse=True)

        # Update state with sorted queue
        state = {**state, "queue": queue}

        # Log top URLs for debugging
        logger.debug(f"Queue sorted by priority. Top 5 URLs:")
        for i, item in enumerate(queue[:5]):
            logger.debug(f"  {i+1}. [{item.get('priority_score', 0.0):.1f}] {item['url']}")

    config = state["config"]

    # CRITICAL: Compute allowed URLs BEFORE agent invocation
    # This enables deterministic stop condition and tool-level gating
    analyzed_keys = {url_key(u) for u in state.get("analyzed_urls", set())}

    # Filter queue to remove analyzed URLs (by canonical key)
    queue = state.get("queue", [])
    queue_candidates = [
        item["url"] for item in queue
        if url_key(item["url"]) not in analyzed_keys
    ]

    # E5: Filter disallowed URLs when respect_robots is enabled
    if config.respect_robots:
        seed_url_for_robots = state["seed_url"]
        disallowed_paths = get_robots_disallowed_paths(seed_url_for_robots)
        if disallowed_paths:
            pre_filter_count = len(queue_candidates)
            queue_candidates = [
                url for url in queue_candidates
                if not is_robots_disallowed(url, disallowed_paths)
            ]
            filtered_count = pre_filter_count - len(queue_candidates)
            if filtered_count > 0:
                logger.info(f"E5 robots.txt: Filtered {filtered_count} URLs (disallowed by robots.txt)")

    # Allowed = top K from queue + seed if not analyzed
    allowed_urls = queue_candidates[:10]  # K=10

    # Include seed URL only if not analyzed yet
    seed_url = state["seed_url"]
    if url_key(seed_url) not in analyzed_keys and seed_url not in allowed_urls:
        allowed_urls = [seed_url] + allowed_urls[:9]  # Keep K=10 total

    # Deterministic stop: if no allowed URLs, stop immediately without invoking agent
    # BUT: Validate minimum discovery thresholds first (prevent premature stopping)
    if not allowed_urls:
        # Check if minimum thresholds are met
        pages_analyzed = len(state.get("analyzed_urls", set()))
        api_calls_found = len(state.get("candidate_api_calls", []))
        endpoints_found = len(state.get("endpoints", []))

        thresholds_met = (
            pages_analyzed >= config.min_pages_before_stop and
            api_calls_found >= config.min_candidate_api_calls
        )

        if not thresholds_met:
            logger.warning(
                f"Stop requested but minimum thresholds NOT met: "
                f"pages={pages_analyzed}/{config.min_pages_before_stop}, "
                f"api_calls={api_calls_found}/{config.min_candidate_api_calls}, "
                f"endpoints={endpoints_found}"
            )
            logger.warning(
                "Minimum thresholds not met but queue is empty. "
                "This indicates insufficient discovery - allowing stop but flagging as incomplete."
            )

        logger.info("No unanalyzed URLs remaining. Stopping without agent invocation.")
        return {
            "next_action": "stop",
            "stop_reason": (
                "All queue URLs have been analyzed"
                if thresholds_met
                else "Queue empty (insufficient discovery - thresholds not met)"
            ),
            "planner_agent": state.get("planner_agent")  # Preserve agent if exists
        }

    logger.info(f"Allowed URLs for this invocation: {len(allowed_urls)}")
    logger.debug(f"Allowed URLs: {allowed_urls[:3]}...")

    # Create filtered tools that capture allowed_urls + analyzed_keys
    def create_filtered_tools(allowed_urls: list[str], analyzed_keys: set[str]):
        """Create tools with gating logic for this invocation.

        Tools will block:
        - URLs already analyzed (by canonical key)
        - URLs not in allowed set

        Returns tools with preserved names for parsing compatibility.
        """
        allowed_keys = {url_key(u) for u in allowed_urls}

        # Wrap render_page_with_js
        def filtered_render(url: str) -> dict:
            """Render page with JS (gated version)."""
            key = url_key(url)

            # Check if already analyzed
            if key in analyzed_keys:
                logger.warning(f"BLOCKED RENDER (pre-fetch): {url} - already analyzed")
                return {
                    "blocked": True,
                    "tool": "render_page_with_js",
                    "url": url,
                    "url_key": key,
                    "reason": "already_analyzed",
                    "allowed_urls": allowed_urls[:5],
                    "message": f"URL was already analyzed. Pick from queue: {allowed_urls[:3]}"
                }

            # Check if in allowed set
            if key not in allowed_keys:
                logger.warning(f"BLOCKED RENDER (pre-fetch): {url} - not in allowed set")
                return {
                    "blocked": True,
                    "tool": "render_page_with_js",
                    "url": url,
                    "url_key": key,
                    "reason": "not_allowed",
                    "allowed_urls": allowed_urls[:5],
                    "message": f"URL not in allowed set. Pick from queue: {allowed_urls[:3]}"
                }

            # Allowed - proceed with normal render
            logger.info(f"Rendering allowed URL: {url}")
            return render_page_with_js.func(url)

        # Set function name and decorate
        filtered_render.__name__ = "render_page_with_js"
        filtered_render_tool = tool(filtered_render)

        # Wrap extract_links (also expensive browser call)
        def filtered_extract(url: str) -> dict:
            """Extract links (gated version)."""
            key = url_key(url)

            # Same gating logic
            if key in analyzed_keys:
                logger.warning(f"BLOCKED EXTRACT_LINKS (pre-fetch): {url} - already analyzed")
                return {
                    "blocked": True,
                    "tool": "extract_links",
                    "url": url,
                    "url_key": key,
                    "reason": "already_analyzed",
                    "allowed_urls": allowed_urls[:5],
                    "message": f"URL was already analyzed. Pick from queue: {allowed_urls[:3]}"
                }

            if key not in allowed_keys:
                logger.warning(f"BLOCKED EXTRACT_LINKS (pre-fetch): {url} - not in allowed set")
                return {
                    "blocked": True,
                    "tool": "extract_links",
                    "url": url,
                    "url_key": key,
                    "reason": "not_allowed",
                    "allowed_urls": allowed_urls[:5],
                    "message": f"URL not in allowed set. Pick from queue: {allowed_urls[:3]}"
                }

            # Allowed - proceed
            logger.info(f"Extracting links from allowed URL: {url}")
            return extract_links.func(url)

        # Set function name and decorate
        filtered_extract.__name__ = "extract_links"
        filtered_extract_tool = tool(filtered_extract)

        return [filtered_render_tool, filtered_extract_tool, http_get_headers]

    # Create filtered tools for this invocation
    tools = create_filtered_tools(allowed_urls, analyzed_keys)

    # Always recreate agent with fresh filtered tools (tools change each invocation)
    logger.info("Creating planner_react agent with filtered tools for this invocation")

    # Create fast model for planner (Haiku, no extended thinking)
    factory = LLMFactory(config=config, region=config.aws_region)
    llm = factory.create_fast_model()

    # System prompt with critical constraints
    system_prompt = SystemMessage(content="""You are a planning agent for web scraping and API discovery.

Your goal: Analyze websites to discover API endpoints, documentation, and data sources.

Available tools:
- render_page_with_js: Use for JavaScript-heavy pages (SPAs, React apps, portals)
- http_get_headers: Quick check of HTTP status and headers
- extract_links: Extract all links from a page

Decision-making strategy:
1. For URLs with "portal", "app" in domain → use render_page_with_js
2. For empty pages or 0 links returned → use render_page_with_js
3. Prioritize links with "api", "docs", "endpoint", "data" keywords
4. Stop when sufficient endpoints found

Critical constraints:
- NEVER call render_page_with_js on the same URL twice
- ONLY use URLs explicitly shown in the queue from your context
- If a URL is in "Already Analyzed" section, do NOT visit it again
- If all queue URLs are analyzed, stop exploration

Always reason step-by-step about which tool to use and why.""")

    # Create agent with filtered tools
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=MemorySaver(),
    )
    logger.info("Created planner_react agent with filtered tools")

    # Build context message for agent
    primary_api_name = state.get('primary_api_name')

    # Build focus control instructions
    focus_instructions = ""
    if primary_api_name:
        focus_instructions = f"""
CRITICAL FOCUS RULES:
- Primary API: "{primary_api_name}" (from seed URL fragment)
- ONLY visit pages related to this specific API
- IGNORE links to other APIs/products until this API is fully documented
- Stay anchored to pages that mention "{primary_api_name}" in their content
"""
    else:
        focus_instructions = """
CRITICAL FOCUS RULES:
- Stay within the same domain/portal as the seed URL
- Focus on pages directly related to the seed URL content
- IGNORE tangential links that lead away from the main data source
"""

    context = f"""Current analysis state:
- Seed URL: {state['seed_url']}
- Pages visited: {len(state['visited'])}/{config.max_steps}
- Current depth: {state['current_depth']}/{state['max_depth']}
- Endpoints found: {len(state['endpoints'])}
- Queue size: {len(state['queue'])}
{focus_instructions}
Recent findings:
{format_recent_findings(state)}
{format_analyzed_urls(state)}
Top links in queue:
{format_queue_links(state)}

Decide next action:
1. Pick ONE URL from "Top links in queue" above (MUST be from that list)
2. Call render_page_with_js with that URL
3. Reason about what you learned and decide next steps

⚠️ IMPORTANT: Only explore URLs from the queue. Tools will block revisits to analyzed URLs.
If queue is empty, stop exploration.

Reason step-by-step about which URL to explore next.
REMEMBER: Stay focused on the primary API/data source - do not wander to other APIs or unrelated content.
"""

    # Invoke agent with ReAct pattern
    try:
        logger.info("Invoking agent with ReAct pattern")

        # Get full message history from checkpointer and trim to prevent context overflow
        thread_config = {"configurable": {"thread_id": f"analysis-{state['seed_url']}"}}
        try:
            agent_state = agent.get_state(config=thread_config)
            full_messages = agent_state.values.get("messages", []) if hasattr(agent_state, 'values') else []
        except Exception as e:
            logger.debug(f"Could not retrieve agent state (may be first invocation): {e}")
            full_messages = []

        # Trim message history to prevent context overflow
        trimmed_messages = trim_message_history(full_messages, max_messages=12)
        logger.info(f"Message history: {len(full_messages)} total, {len(trimmed_messages)} after trim")

        # Invoke with trimmed history
        result = agent.invoke(
            {"messages": trimmed_messages + [HumanMessage(content=context)]},
            config=thread_config
        )

        logger.info(f"Agent invocation complete, processing {len(result['messages'])} messages")

        # Extract artifacts from tool results
        extracted = extract_artifacts_from_messages(result["messages"], state)
        logger.info(
            "Extracted from agent tools: %d artifacts, %d screenshots, %d visited URLs, %d candidate API calls",
            len(extracted["artifacts"]),
            len(extracted["screenshots"]),
            len(extracted["visited"]),
            len(extracted["candidate_api_calls"])
        )

        # Parse agent decision from messages
        decision = parse_agent_decision(result["messages"], state)

        logger.info(
            "Agent decision: action=%s, url=%s, reason=%s",
            decision["action"],
            decision["url"],
            decision.get("reason")
        )

        # Merge artifacts with existing state
        updated_artifacts = {**state.get("artifacts", {}), **extracted["artifacts"]}
        updated_screenshots = {**state.get("screenshots", {}), **extracted["screenshots"]}
        updated_visited = state.get("visited", set()) | extracted["visited"]
        # candidate_api_calls will accumulate via operator.add
        updated_candidate_api_calls = extracted["candidate_api_calls"]

        # Promote candidate API calls to queue with high scores
        updated_queue = list(state.get("queue", []))
        existing_queue_urls = {item["url"] for item in updated_queue}

        for api_call in updated_candidate_api_calls:
            if api_call not in existing_queue_urls:
                # Add with high score (0.9) to prioritize API discovery
                updated_queue.append({
                    "url": api_call,
                    "score": 0.9,  # High priority for API calls
                    "reason": "network_call_discovery (API endpoint detected in traffic)"
                })
                existing_queue_urls.add(api_call)

        if len(updated_candidate_api_calls) > 0:
            logger.info(
                f"Promoted {len(updated_candidate_api_calls)} candidate API calls to queue "
                f"(queue size: {len(state.get('queue', []))} → {len(updated_queue)})"
            )

    except Exception as e:
        logger.error("Agent invocation failed: %s", str(e), exc_info=True)
        # Fallback: stop safely
        decision = {
            "action": "stop",
            "url": None,
            "reason": f"Agent invocation failed: {str(e)}"
        }
        updated_artifacts = state.get("artifacts", {})
        updated_screenshots = state.get("screenshots", {})
        updated_visited = state.get("visited", set())
        updated_candidate_api_calls = []
        updated_queue = state.get("queue", [])

    # Validate stop decision against minimum thresholds
    if decision["action"] == "stop":
        # Check if minimum discovery thresholds are met
        pages_analyzed = len(state.get("analyzed_urls", set()))
        api_calls_found = len(updated_candidate_api_calls) + len(state.get("candidate_api_calls", []))
        endpoints_found = len(state.get("endpoints", []))

        thresholds_met = (
            pages_analyzed >= config.min_pages_before_stop and
            api_calls_found >= config.min_candidate_api_calls
        )

        # Check if queue has high-value unanalyzed candidates
        high_value_candidates = [
            item for item in updated_queue
            if item.get("score", 0) >= config.high_value_threshold
        ]

        if not thresholds_met or high_value_candidates:
            logger.warning(
                f"Agent wants to stop but thresholds not met or queue has candidates: "
                f"pages={pages_analyzed}/{config.min_pages_before_stop}, "
                f"api_calls={api_calls_found}/{config.min_candidate_api_calls}, "
                f"endpoints={endpoints_found}, "
                f"high_value_queue={len(high_value_candidates)}"
            )

            if high_value_candidates:
                logger.info(
                    f"Overriding agent stop decision - {len(high_value_candidates)} high-value "
                    f"candidates remain in queue. Continuing exploration."
                )
                decision = {
                    "action": "continue",
                    "url": None,
                    "reason": "Stop overridden - high-value candidates remain in queue"
                }
            elif not thresholds_met:
                logger.info(
                    f"Overriding agent stop decision - minimum thresholds not met. "
                    f"Continuing exploration."
                )
                decision = {
                    "action": "continue",
                    "url": None,
                    "reason": "Stop overridden - minimum discovery thresholds not met"
                }

    return {
        "next_action": decision["action"],
        "current_url": decision["url"],
        "stop_reason": decision.get("reason") if decision["action"] == "stop" else None,
        # Don't store agent - causes serialization issues with checkpointer
        # Agent will be recreated on next invocation
        "artifacts": updated_artifacts,  # Update with new artifacts
        "screenshots": updated_screenshots,  # Update with new screenshots
        "visited": updated_visited,  # Update visited set
        "candidate_api_calls": updated_candidate_api_calls,  # API calls from network traffic
        "queue": updated_queue,  # Updated queue with promoted API calls
    }


# Export public API
__all__ = [
    "create_planner_react_agent",
    "planner_react_node",
]
