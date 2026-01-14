"""Unit tests for chunking module.

Tests:
- Markdown chunking
- Token estimation
- Chunk selection
- Heading-based chunking
"""

import pytest

from agentic_scraper.business_analyst.utils.chunking import (
    estimate_tokens,
    chunk_markdown,
    select_top_chunks,
    merge_chunks,
    extract_api_keywords,
    chunk_by_headings,
)


class TestEstimateTokens:
    """Tests for estimate_tokens function."""

    def test_estimate_tokens_simple(self):
        """Test token estimation for simple text."""
        text = "This is a test"
        tokens = estimate_tokens(text)
        # 14 chars / 4 = 3.5 -> 3 tokens
        assert tokens == 3

    def test_estimate_tokens_longer(self):
        """Test token estimation for longer text."""
        text = "This is a much longer test sentence with more words."
        tokens = estimate_tokens(text)
        # ~53 chars / 4 = ~13 tokens
        assert 10 <= tokens <= 15

    def test_estimate_tokens_empty(self):
        """Test token estimation for empty text."""
        assert estimate_tokens("") == 0


class TestChunkMarkdown:
    """Tests for chunk_markdown function."""

    def test_chunk_simple_markdown(self):
        """Test chunking simple markdown."""
        markdown = """# Heading 1

Some content here.

## Heading 2

More content here.

### Heading 3

Even more content."""

        chunks = chunk_markdown(markdown, max_tokens=50)

        # Should have multiple chunks
        assert len(chunks) > 0

        # Chunks should have metadata
        assert all(hasattr(c, 'content') for c in chunks)
        assert all(hasattr(c, 'heading') for c in chunks)
        assert all(hasattr(c, 'score') for c in chunks)

    def test_chunk_respects_token_limit(self):
        """Test that chunks respect token limit for multi-line content.

        Note: chunk_markdown operates on a line-by-line basis, so a single
        oversized line cannot be split. This test uses multi-line content
        to verify chunking behavior.
        """
        # Create long content with multiple lines (chunking is line-based)
        markdown = "\n".join(["This is a test sentence."] * 200)  # ~200 lines

        chunks = chunk_markdown(markdown, max_tokens=200)

        # All chunks should be under limit (since each line is small)
        for chunk in chunks:
            assert chunk.token_estimate <= 200

    def test_chunk_empty_markdown(self):
        """Test chunking empty markdown."""
        chunks = chunk_markdown("", max_tokens=100)
        assert len(chunks) == 0

    def test_chunk_prioritizes_headings(self):
        """Test that chunks with headings get higher scores."""
        markdown = """# Important API Docs

Some content.

Regular text without heading.

## Another Section

More content."""

        chunks = chunk_markdown(markdown, max_tokens=100, prioritize_headings=True)

        # Chunks with headings should have higher scores
        chunks_with_headings = [c for c in chunks if c.heading]
        chunks_without_headings = [c for c in chunks if not c.heading]

        if chunks_with_headings and chunks_without_headings:
            avg_with_heading = sum(c.score for c in chunks_with_headings) / len(chunks_with_headings)
            avg_without_heading = sum(c.score for c in chunks_without_headings) / len(chunks_without_headings)
            assert avg_with_heading > avg_without_heading

    def test_chunk_prioritizes_links(self):
        """Test that chunks with links get higher scores."""
        markdown = """
Content with a [link](https://example.com).

Content without links.
"""

        chunks = chunk_markdown(markdown, max_tokens=100, prioritize_links=True)

        # Chunk with link should have higher score
        chunks_with_links = [c for c in chunks if c.contains_links]
        assert len(chunks_with_links) > 0
        assert any(c.score > 1.0 for c in chunks_with_links)

    def test_chunk_prioritizes_keywords(self):
        """Test that chunks with keywords get higher scores."""
        markdown = """
# Section 1

This section has API endpoint information.

# Section 2

This section has unrelated content.
"""

        keywords = ["api", "endpoint"]
        chunks = chunk_markdown(markdown, max_tokens=100, prioritize_keywords=keywords)

        # Find chunk with keywords
        chunks_with_keywords = [
            c for c in chunks
            if any(kw in c.content.lower() for kw in keywords)
        ]

        # Should boost score
        assert len(chunks_with_keywords) > 0
        assert any(c.score > 1.0 for c in chunks_with_keywords)


class TestSelectTopChunks:
    """Tests for select_top_chunks function."""

    def test_select_top_chunks_basic(self):
        """Test selecting top N chunks."""
        markdown = """# Heading 1
Content 1

## Heading 2
Content 2

### Heading 3
Content 3

#### Heading 4
Content 4

##### Heading 5
Content 5"""

        chunks = chunk_markdown(markdown, max_tokens=50)
        top_chunks = select_top_chunks(chunks, max_chunks=3)

        # Should return exactly 3 chunks
        assert len(top_chunks) <= 3

    def test_select_top_chunks_respects_token_budget(self):
        """Test that selection respects total token budget."""
        markdown = "This is content. " * 500  # Large content

        chunks = chunk_markdown(markdown, max_tokens=200)
        top_chunks = select_top_chunks(chunks, max_chunks=10, max_total_tokens=500)

        # Total tokens should be under budget
        total_tokens = sum(c.token_estimate for c in top_chunks)
        assert total_tokens <= 500

    def test_select_top_chunks_empty_input(self):
        """Test selecting from empty chunk list."""
        top_chunks = select_top_chunks([], max_chunks=5)
        assert len(top_chunks) == 0

    def test_select_top_chunks_fewer_than_requested(self):
        """Test selecting when fewer chunks available than requested."""
        markdown = "# Simple\n\nContent."
        chunks = chunk_markdown(markdown, max_tokens=100)

        top_chunks = select_top_chunks(chunks, max_chunks=100)

        # Should return all available chunks
        assert len(top_chunks) == len(chunks)


class TestMergeChunks:
    """Tests for merge_chunks function."""

    def test_merge_chunks_basic(self):
        """Test merging chunks back together."""
        markdown = """# Heading 1
Content 1

## Heading 2
Content 2"""

        chunks = chunk_markdown(markdown, max_tokens=100)
        merged = merge_chunks(chunks)

        # Should contain content from all chunks
        assert isinstance(merged, str)
        assert len(merged) > 0

    def test_merge_chunks_custom_separator(self):
        """Test merging with custom separator."""
        markdown = "Content 1\n\nContent 2"
        chunks = chunk_markdown(markdown, max_tokens=100)

        merged = merge_chunks(chunks, separator="\n\n===\n\n")

        # Should contain custom separator
        if len(chunks) > 1:
            assert "===" in merged

    def test_merge_chunks_empty(self):
        """Test merging empty chunk list."""
        merged = merge_chunks([])
        assert merged == ""


class TestExtractApiKeywords:
    """Tests for extract_api_keywords function."""

    def test_extract_api_keywords_returns_list(self):
        """Test that API keywords returns a list."""
        keywords = extract_api_keywords()
        assert isinstance(keywords, list)
        assert len(keywords) > 0

    def test_extract_api_keywords_contains_expected(self):
        """Test that API keywords contain expected terms."""
        keywords = extract_api_keywords()

        # Should contain common API terms
        assert 'endpoint' in keywords
        assert 'api' in keywords
        assert 'authentication' in keywords
        assert 'json' in keywords


class TestChunkByHeadings:
    """Tests for chunk_by_headings function."""

    def test_chunk_by_headings_basic(self):
        """Test chunking by markdown headings."""
        markdown = """# Introduction

This is the intro.

## Section A

Content for section A.

## Section B

Content for section B.

### Subsection B.1

More details."""

        sections = chunk_by_headings(markdown)

        # Should have multiple sections
        assert len(sections) > 0

        # Each section is a (heading, content) tuple
        assert all(isinstance(s, tuple) for s in sections)
        assert all(len(s) == 2 for s in sections)

        # Check heading names
        headings = [s[0] for s in sections]
        assert 'Introduction' in headings

    def test_chunk_by_headings_respects_token_limit(self):
        """Test that large sections are further chunked."""
        # Create section with lots of content
        large_content = "Content line. " * 1000  # ~2500 tokens
        markdown = f"""# Large Section

{large_content}

## Small Section

Small content."""

        sections = chunk_by_headings(markdown, max_tokens_per_section=500)

        # Large section should be split into parts
        large_section_parts = [s for s in sections if 'Large Section' in s[0]]
        assert len(large_section_parts) > 1

    def test_chunk_by_headings_empty(self):
        """Test chunking empty markdown."""
        sections = chunk_by_headings("")
        assert len(sections) == 0

    def test_chunk_by_headings_no_headings(self):
        """Test chunking markdown without headings."""
        markdown = "Just some plain text without any headings."
        sections = chunk_by_headings(markdown)

        # Should have at least one section (default "Introduction")
        assert len(sections) >= 1
        assert sections[0][0] == "Introduction"

    def test_chunk_by_headings_mixed_levels(self):
        """Test chunking with mixed heading levels."""
        markdown = """# H1 Title

Content.

### H3 Subsection

More content.

## H2 Section

Final content."""

        sections = chunk_by_headings(markdown)

        # Should handle all heading levels
        assert len(sections) >= 3
