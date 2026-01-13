"""Markdown chunking utilities for BA Analyst - Token-aware content splitting.

This module provides utilities for:
- Chunking large markdown documents to fit within token limits
- Prioritizing chunks based on relevance (headings, links, keywords)
- Selecting top chunks for analysis
"""

import logging
import re
from typing import List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MarkdownChunk:
    """A chunk of markdown content with metadata."""
    content: str
    start_line: int
    end_line: int
    heading: Optional[str] = None
    score: float = 0.0
    contains_links: bool = False
    contains_code: bool = False
    token_estimate: int = 0


def estimate_tokens(text: str) -> int:
    """Estimate token count for text.

    Uses a simple heuristic: ~4 characters per token (Claude's average).
    This is approximate but sufficient for chunking decisions.

    Args:
        text: Text to estimate

    Returns:
        Estimated token count

    Example:
        >>> tokens = estimate_tokens("This is a test sentence.")
        >>> print(tokens)
        6
    """
    # Simple heuristic: 4 chars per token on average
    return len(text) // 4


def chunk_markdown(
    text: str,
    max_tokens: int = 2000,
    prioritize_headings: bool = True,
    prioritize_links: bool = True,
    prioritize_keywords: Optional[List[str]] = None
) -> List[MarkdownChunk]:
    """Chunk markdown text into token-limited segments.

    Splits markdown intelligently by:
    1. Respecting markdown structure (don't split mid-heading)
    2. Keeping related content together
    3. Scoring chunks by relevance

    Args:
        text: Markdown text to chunk
        max_tokens: Maximum tokens per chunk (default: 2000)
        prioritize_headings: Give higher scores to chunks with headings
        prioritize_links: Give higher scores to chunks with links
        prioritize_keywords: List of keywords to boost chunk scores

    Returns:
        List of MarkdownChunk objects, sorted by relevance score

    Example:
        >>> markdown = "# API Docs\\n\\nSome content...\\n## Endpoint A\\n..."
        >>> chunks = chunk_markdown(markdown, max_tokens=500)
        >>> print(len(chunks))
        3
        >>> print(chunks[0].heading)
        'API Docs'
    """
    if not text or not text.strip():
        logger.warning("Empty text provided to chunk_markdown")
        return []

    if prioritize_keywords is None:
        prioritize_keywords = []

    lines = text.split('\n')
    chunks = []
    current_chunk_lines = []
    current_heading = None
    current_start_line = 0
    current_tokens = 0

    for i, line in enumerate(lines):
        line_tokens = estimate_tokens(line)

        # Check if adding this line would exceed limit
        if current_tokens + line_tokens > max_tokens and current_chunk_lines:
            # Save current chunk
            chunk_content = '\n'.join(current_chunk_lines)
            chunk = MarkdownChunk(
                content=chunk_content,
                start_line=current_start_line,
                end_line=i - 1,
                heading=current_heading,
                token_estimate=current_tokens
            )
            chunks.append(chunk)

            # Start new chunk
            current_chunk_lines = [line]
            current_start_line = i
            current_tokens = line_tokens

            # Check if this line is a heading
            if line.startswith('#'):
                current_heading = line.lstrip('#').strip()
        else:
            current_chunk_lines.append(line)
            current_tokens += line_tokens

            # Update heading if this is a heading line
            if line.startswith('#'):
                current_heading = line.lstrip('#').strip()

    # Save final chunk
    if current_chunk_lines:
        chunk_content = '\n'.join(current_chunk_lines)
        chunk = MarkdownChunk(
            content=chunk_content,
            start_line=current_start_line,
            end_line=len(lines) - 1,
            heading=current_heading,
            token_estimate=current_tokens
        )
        chunks.append(chunk)

    # Score chunks based on content
    for chunk in chunks:
        score = 0.0

        # Base score
        score += 1.0

        # Prioritize chunks with headings
        if prioritize_headings and chunk.heading:
            score += 2.0

        # Prioritize chunks with links
        if prioritize_links and ('[' in chunk.content and '](' in chunk.content):
            chunk.contains_links = True
            score += 1.5

        # Prioritize chunks with code blocks (API endpoints often in code)
        if '```' in chunk.content or '`' in chunk.content:
            chunk.contains_code = True
            score += 1.0

        # Prioritize chunks with keywords
        for keyword in prioritize_keywords:
            if keyword.lower() in chunk.content.lower():
                score += 0.5

        chunk.score = score

    # Sort by score (highest first)
    chunks.sort(key=lambda c: c.score, reverse=True)

    logger.info(
        f"Chunked markdown into {len(chunks)} chunks "
        f"(avg {sum(c.token_estimate for c in chunks) // len(chunks) if chunks else 0} tokens/chunk)"
    )

    return chunks


def select_top_chunks(
    chunks: List[MarkdownChunk],
    max_chunks: int = 10,
    max_total_tokens: Optional[int] = None
) -> List[MarkdownChunk]:
    """Select top N chunks by relevance score.

    Optionally enforces a total token budget across all selected chunks.

    Args:
        chunks: List of MarkdownChunk objects (assumed sorted by score)
        max_chunks: Maximum number of chunks to return
        max_total_tokens: Optional maximum total tokens across all chunks

    Returns:
        List of top-scoring chunks that fit within constraints

    Example:
        >>> chunks = chunk_markdown(text, max_tokens=500)
        >>> top_chunks = select_top_chunks(chunks, max_chunks=5, max_total_tokens=3000)
        >>> print(len(top_chunks))
        5
        >>> print(sum(c.token_estimate for c in top_chunks))
        2847
    """
    if not chunks:
        return []

    selected = []
    total_tokens = 0

    for chunk in chunks:
        # Check chunk limit
        if len(selected) >= max_chunks:
            break

        # Check token budget
        if max_total_tokens and total_tokens + chunk.token_estimate > max_total_tokens:
            logger.info(
                f"Stopping chunk selection: Would exceed token budget "
                f"({total_tokens + chunk.token_estimate} > {max_total_tokens})"
            )
            break

        selected.append(chunk)
        total_tokens += chunk.token_estimate

    logger.info(
        f"Selected {len(selected)} chunks "
        f"(total {total_tokens} tokens, avg score {sum(c.score for c in selected) / len(selected):.2f})"
    )

    return selected


def merge_chunks(chunks: List[MarkdownChunk], separator: str = "\n\n---\n\n") -> str:
    """Merge multiple chunks back into a single text.

    Args:
        chunks: List of MarkdownChunk objects to merge
        separator: String to insert between chunks (default: horizontal rule)

    Returns:
        Merged text

    Example:
        >>> chunks = [chunk1, chunk2, chunk3]
        >>> merged = merge_chunks(chunks)
        >>> print(merged)
        # Content of chunk1
        ---
        # Content of chunk2
        ---
        # Content of chunk3
    """
    if not chunks:
        return ""

    return separator.join(chunk.content for chunk in chunks)


def extract_api_keywords() -> List[str]:
    """Get default API-related keywords for prioritization.

    Returns:
        List of API-related keywords

    Example:
        >>> keywords = extract_api_keywords()
        >>> print(keywords[:5])
        ['endpoint', 'api', 'parameter', 'response', 'request']
    """
    return [
        'endpoint', 'api', 'parameter', 'response', 'request',
        'method', 'get', 'post', 'put', 'delete', 'patch',
        'authentication', 'auth', 'token', 'key', 'bearer',
        'json', 'xml', 'csv', 'format',
        'example', 'sample', 'curl',
        'http', 'https', 'url', 'uri',
        'header', 'body', 'query', 'path',
        'status', 'code', '200', '401', '403', '404'
    ]


def chunk_by_headings(
    text: str,
    max_tokens_per_section: int = 3000
) -> List[Tuple[str, str]]:
    """Chunk markdown by heading sections.

    Splits text at markdown headings and returns (heading, content) pairs.
    Each section is further chunked if it exceeds max_tokens_per_section.

    Args:
        text: Markdown text
        max_tokens_per_section: Max tokens per heading section

    Returns:
        List of (heading, content) tuples

    Example:
        >>> text = "# Intro\\nContent...\\n## Section A\\nMore...\\n## Section B\\nEven more..."
        >>> sections = chunk_by_headings(text)
        >>> print(len(sections))
        3
        >>> print(sections[0][0])
        'Intro'
    """
    if not text or not text.strip():
        return []

    # Split by markdown headings
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

    sections = []
    current_heading = "Introduction"
    current_content = []

    lines = text.split('\n')

    for line in lines:
        match = heading_pattern.match(line)
        if match:
            # Save previous section
            if current_content:
                content = '\n'.join(current_content)
                tokens = estimate_tokens(content)

                # Further chunk if too large
                if tokens > max_tokens_per_section:
                    # Split into smaller chunks
                    sub_chunks = chunk_markdown(content, max_tokens=max_tokens_per_section)
                    for i, chunk in enumerate(sub_chunks):
                        section_name = f"{current_heading} (part {i+1})"
                        sections.append((section_name, chunk.content))
                else:
                    sections.append((current_heading, content))

            # Start new section
            current_heading = match.group(2).strip()
            current_content = []
        else:
            current_content.append(line)

    # Save final section
    if current_content:
        content = '\n'.join(current_content)
        tokens = estimate_tokens(content)

        if tokens > max_tokens_per_section:
            sub_chunks = chunk_markdown(content, max_tokens=max_tokens_per_section)
            for i, chunk in enumerate(sub_chunks):
                section_name = f"{current_heading} (part {i+1})"
                sections.append((section_name, chunk.content))
        else:
            sections.append((current_heading, content))

    logger.info(f"Chunked markdown into {len(sections)} heading-based sections")
    return sections
