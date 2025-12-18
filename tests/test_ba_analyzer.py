"""Unit tests for BA analyzer.

Tests the BAAnalyzer class with mocked dependencies.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from claude_scraper.agents.ba_analyzer import BAAnalyzer
from claude_scraper.tools.web_fetch import WebFetchTool
from claude_scraper.tools.puppeteer import PuppeteerTool
from claude_scraper.storage.repository import AnalysisRepository
from baml_client.types import (
    Phase0Detection,
    Phase1Documentation,
    Phase2Tests,
    ValidatedSpec,
    DataSourceType,
    HTTPMethod,
    AuthenticationMethod,
    ValidationStatus,
    ConfidenceLevel,
    DocQuality,
    ScraperType,
    ComplexityLevel,
    ResponseFormat,
)


@pytest.fixture
def mock_web_fetch():
    """Create mock WebFetchTool."""
    mock = Mock(spec=WebFetchTool)
    mock.fetch.return_value = "<html>API documentation</html>"
    return mock


@pytest.fixture
def mock_puppeteer():
    """Create mock PuppeteerTool."""
    mock = Mock(spec=PuppeteerTool)
    mock.extract_network_calls.return_value = [
        "https://api.example.com/v1/data",
        "https://api.example.com/v1/users",
    ]
    return mock


@pytest.fixture
def mock_repository(tmp_path):
    """Create mock repository with temp directory."""
    return AnalysisRepository(tmp_path / "datasource_analysis")


@pytest.fixture
def analyzer(mock_web_fetch, mock_puppeteer, mock_repository):
    """Create BAAnalyzer with mocked dependencies."""
    return BAAnalyzer(
        web_fetch=mock_web_fetch,
        puppeteer=mock_puppeteer,
        repository=mock_repository,
    )


class TestBAAnalyzerInit:
    """Tests for BAAnalyzer initialization."""

    def test_init_with_all_dependencies(
        self, mock_web_fetch, mock_puppeteer, mock_repository
    ):
        """Test initialization with all dependencies."""
        analyzer = BAAnalyzer(
            web_fetch=mock_web_fetch,
            puppeteer=mock_puppeteer,
            repository=mock_repository,
        )
        assert analyzer.web_fetch == mock_web_fetch
        assert analyzer.puppeteer == mock_puppeteer
        assert analyzer.repository == mock_repository

    def test_init_without_puppeteer(self, mock_web_fetch, mock_repository):
        """Test initialization without Puppeteer (optional)."""
        analyzer = BAAnalyzer(
            web_fetch=mock_web_fetch,
            repository=mock_repository,
        )
        assert analyzer.web_fetch == mock_web_fetch
        assert analyzer.puppeteer is None
        assert analyzer.repository == mock_repository

    def test_init_without_repository(self, mock_web_fetch):
        """Test initialization without repository (uses default)."""
        analyzer = BAAnalyzer(web_fetch=mock_web_fetch)
        assert analyzer.web_fetch == mock_web_fetch
        assert analyzer.repository is not None
        assert analyzer.repository.base_dir == "datasource_analysis"

    def test_init_requires_web_fetch(self):
        """Test that web_fetch is required."""
        with pytest.raises(ValueError, match="web_fetch cannot be None"):
            BAAnalyzer(web_fetch=None)


class TestAnalyzePhase0:
    """Tests for Phase 0: Detection."""

    @pytest.mark.asyncio
    async def test_analyze_phase0_success(self, analyzer, mock_web_fetch, mock_puppeteer):
        """Test successful Phase 0 analysis."""
        # Mock the BAML function call
        mock_phase0 = Phase0Detection(
            detected_type=DataSourceType.API,
            confidence=0.9,
            indicators=["Found REST endpoints", "OpenAPI documentation visible"],
            discovered_api_calls=[
                "https://api.example.com/v1/data",
                "https://api.example.com/v1/users",
            ],
            endpoints=[],
            url="https://api.example.com",
        )

        with patch("claude_scraper.agents.ba_analyzer.b.AnalyzePhase0", new_callable=AsyncMock) as mock_baml:
            mock_baml.return_value = mock_phase0

            result = await analyzer.analyze_phase0("https://api.example.com")

            # Verify result
            assert result.detected_type == DataSourceType.API
            assert result.confidence == 0.9
            assert len(result.discovered_api_calls) == 2

            # Verify tools were called
            mock_web_fetch.fetch.assert_called_once()
            mock_puppeteer.extract_network_calls.assert_called_once_with(
                "https://api.example.com"
            )

            # Verify BAML function was called
            mock_baml.assert_called_once()
            call_args = mock_baml.call_args[1]
            assert call_args["url"] == "https://api.example.com"
            assert len(call_args["network_calls"]) == 2

    @pytest.mark.asyncio
    async def test_analyze_phase0_empty_url(self, analyzer):
        """Test Phase 0 with empty URL."""
        with pytest.raises(ValueError, match="url cannot be empty"):
            await analyzer.analyze_phase0("")

    @pytest.mark.asyncio
    async def test_analyze_phase0_without_puppeteer(
        self, mock_web_fetch, mock_repository
    ):
        """Test Phase 0 without Puppeteer (graceful degradation)."""
        analyzer = BAAnalyzer(
            web_fetch=mock_web_fetch,
            puppeteer=None,
            repository=mock_repository,
        )

        mock_phase0 = Phase0Detection(
            detected_type=DataSourceType.WEBSITE,
            confidence=0.7,
            indicators=["Download links found"],
            discovered_api_calls=[],
            endpoints=[],
            url="https://portal.example.com",
        )

        with patch("claude_scraper.agents.ba_analyzer.b.AnalyzePhase0", new_callable=AsyncMock) as mock_baml:
            mock_baml.return_value = mock_phase0

            result = await analyzer.analyze_phase0("https://portal.example.com")

            assert result.detected_type == DataSourceType.WEBSITE
            mock_web_fetch.fetch.assert_called_once()

            # Verify BAML was called with empty network_calls
            call_args = mock_baml.call_args[1]
            assert call_args["network_calls"] == []


class TestAnalyzePhase1:
    """Tests for Phase 1: Documentation."""

    @pytest.mark.asyncio
    async def test_analyze_phase1_success(self, analyzer, mock_web_fetch):
        """Test successful Phase 1 analysis."""
        phase0 = Phase0Detection(
            detected_type=DataSourceType.API,
            confidence=0.9,
            indicators=[],
            discovered_api_calls=[],
            endpoints=[],
            url="https://api.example.com",
        )

        mock_phase1 = Phase1Documentation(
            source="Documentation Analysis",
            timestamp="2025-01-20T10:00:00Z",
            url="https://api.example.com",
            endpoints=[],
            doc_quality=DocQuality.HIGH,
            notes="Clear documentation",
        )

        with patch("claude_scraper.agents.ba_analyzer.b.AnalyzePhase1", new_callable=AsyncMock) as mock_baml:
            mock_baml.return_value = mock_phase1

            result = await analyzer.analyze_phase1("https://api.example.com", phase0)

            assert result.doc_quality == DocQuality.HIGH
            assert result.url == "https://api.example.com"
            mock_web_fetch.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_phase1_empty_url(self, analyzer):
        """Test Phase 1 with empty URL."""
        phase0 = Phase0Detection(
            detected_type=DataSourceType.API,
            confidence=0.9,
            indicators=[],
            discovered_api_calls=[],
            endpoints=[],
            url="https://api.example.com",
        )

        # Mock the repository save to verify it's not called
        with patch.object(analyzer.repository, 'save') as mock_save:
            with pytest.raises(ValueError, match="url cannot be empty"):
                await analyzer.analyze_phase1("", phase0)

            # Verify repository save was NOT called on error path
            mock_save.assert_not_called()


class TestAnalyzePhase2:
    """Tests for Phase 2: Testing."""

    @pytest.mark.asyncio
    async def test_analyze_phase2_success(self, analyzer):
        """Test successful Phase 2 analysis."""
        phase0 = Phase0Detection(
            detected_type=DataSourceType.API,
            confidence=0.9,
            indicators=[],
            discovered_api_calls=[],
            endpoints=[],
            url="https://api.example.com",
        )

        phase1 = Phase1Documentation(
            source="Documentation Analysis",
            timestamp="2025-01-20T10:00:00Z",
            url="https://api.example.com",
            endpoints=[],
            doc_quality=DocQuality.HIGH,
            notes="",
        )

        # Phase 2 now raises RuntimeError due to Bash tool requirement
        with pytest.raises(RuntimeError, match="Phase 2 testing requires integration"):
            result = await analyzer.analyze_phase2("https://api.example.com", phase0, phase1)


class TestAnalyzePhase3:
    """Tests for Phase 3: Validation."""

    @pytest.mark.asyncio
    async def test_analyze_phase3_success(self, analyzer):
        """Test successful Phase 3 analysis."""
        phase0 = Phase0Detection(
            detected_type=DataSourceType.API,
            confidence=0.9,
            indicators=[],
            discovered_api_calls=[],
            endpoints=[],
            url="https://api.example.com",
        )

        phase1 = Phase1Documentation(
            source="Documentation Analysis",
            timestamp="2025-01-20T10:00:00Z",
            url="https://api.example.com",
            endpoints=[],
            doc_quality=DocQuality.HIGH,
            notes="",
        )

        phase2 = Phase2Tests(
            source="Live Testing",
            timestamp="2025-01-20T10:00:00Z",
            files_saved=[],
        )

        # Import required types for ValidatedSpec
        from baml_client.types import (
            ExecutiveSummary,
            ValidationSummary,
            ScraperRecommendation,
        )

        mock_phase3 = ValidatedSpec(
            source="Validated Specification",
            source_type="API",
            timestamp="2025-01-20T10:00:00Z",
            url="https://api.example.com",
            executive_summary=ExecutiveSummary(
                total_endpoints_discovered=2,
                accessible_endpoints=2,
                success_rate="100%",
                primary_formats=["JSON"],
                authentication_required=False,
                estimated_scraper_complexity=ComplexityLevel.LOW,
            ),
            validation_summary=ValidationSummary(
                phases_completed=["Phase 0", "Phase 1", "Phase 2", "Phase 3"],
                documentation_review="completed",
                live_api_testing="completed",
                discrepancies_found=0,
                confidence_score=0.9,
                confidence_level=ConfidenceLevel.HIGH,
                recommendation="Spec validated",
            ),
            endpoints=[],
            scraper_recommendation=ScraperRecommendation(
                type=ScraperType.API_CLIENT,
                rationale=["Simple REST API"],
                complexity=ComplexityLevel.LOW,
                estimated_effort="2-4 hours",
                key_challenges=[],
            ),
            discrepancies=[],
            artifacts_generated=[],
            next_steps=[],
        )

        with patch("claude_scraper.agents.ba_analyzer.b.AnalyzePhase3", new_callable=AsyncMock) as mock_baml:
            mock_baml.return_value = mock_phase3

            result = await analyzer.analyze_phase3(
                "https://api.example.com", phase0, phase1, phase2
            )

            assert result.validation_summary.confidence_score == 0.9
            assert result.source_type == "API"


class TestRunFullAnalysis:
    """Tests for full 4-phase analysis."""

    @pytest.mark.asyncio
    async def test_run_full_analysis_success(self, analyzer):
        """Test full analysis flow - Phase 2 raises RuntimeError due to Bash tool requirement."""
        # Mock all BAML function calls
        mock_phase0 = Phase0Detection(
            detected_type=DataSourceType.API,
            confidence=0.9,
            indicators=[],
            discovered_api_calls=[],
            endpoints=[],
            url="https://api.example.com",
        )

        mock_phase1 = Phase1Documentation(
            source="Documentation",
            timestamp="2025-01-20T10:00:00Z",
            url="https://api.example.com",
            endpoints=[],
            doc_quality=DocQuality.HIGH,
            notes="",
        )

        with patch("claude_scraper.agents.ba_analyzer.b.AnalyzePhase0", new_callable=AsyncMock) as mock_p0, \
             patch("claude_scraper.agents.ba_analyzer.b.AnalyzePhase1", new_callable=AsyncMock) as mock_p1:

            mock_p0.return_value = mock_phase0
            mock_p1.return_value = mock_phase1

            # Phase 2 now raises RuntimeError which gets wrapped in Exception by run_full_analysis
            with pytest.raises(Exception, match="Phase 2 testing requires integration"):
                result = await analyzer.run_full_analysis("https://api.example.com")

            # Verify Phase 0 and Phase 1 were called before Phase 2 raised error
            mock_p0.assert_called_once()
            mock_p1.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_full_analysis_empty_url(self, analyzer):
        """Test full analysis with empty URL."""
        with pytest.raises(ValueError, match="url cannot be empty"):
            await analyzer.run_full_analysis("")

    @pytest.mark.asyncio
    async def test_analyze_phase1_ftp_source(self, analyzer):
        """Test Phase 1 with FTP source type."""
        phase0 = Phase0Detection(
            detected_type=DataSourceType.FTP,
            confidence=0.9,
            indicators=["ftp:// URLs found"],
            discovered_api_calls=[],
            endpoints=[],
            url="ftp://ftp.example.com",
        )

        # Mock BAML call
        with patch('claude_scraper.agents.ba_analyzer.b.AnalyzePhase1', new_callable=AsyncMock) as mock:
            from baml_client.types import DataInventory
            mock.return_value = Phase1Documentation(
                source="FTP Analysis",
                timestamp="2025-01-20T10:00:00Z",
                url="ftp://ftp.example.com",
                source_type="FTP",
                endpoints=[],
                data_inventory=DataInventory(
                    total_files=10,
                    file_formats=["csv"],
                    categories=["data"],
                    download_links=[]
                ),
                doc_quality=DocQuality.MEDIUM,
                notes="FTP server documentation",
            )

            result = await analyzer.analyze_phase1("ftp://ftp.example.com", phase0)

            assert result.source_type == "FTP"
            assert result.data_inventory is not None

    @pytest.mark.asyncio
    async def test_analyze_phase1_email_source(self, analyzer):
        """Test Phase 1 with EMAIL source type."""
        phase0 = Phase0Detection(
            detected_type=DataSourceType.EMAIL,
            confidence=0.85,
            indicators=["email attachments mentioned"],
            discovered_api_calls=[],
            endpoints=[],
            url="mailto:data@example.com",
        )

        with patch('claude_scraper.agents.ba_analyzer.b.AnalyzePhase1', new_callable=AsyncMock) as mock:
            from baml_client.types import DataInventory
            mock.return_value = Phase1Documentation(
                source="EMAIL Analysis",
                timestamp="2025-01-20T10:00:00Z",
                url="mailto:data@example.com",
                source_type="EMAIL",
                endpoints=[],
                data_inventory=DataInventory(
                    total_files=5,
                    file_formats=["xlsx"],
                    categories=["reports"],
                    download_links=[]
                ),
                doc_quality=DocQuality.MEDIUM,
                notes="Email data source documentation",
            )

            result = await analyzer.analyze_phase1("mailto:data@example.com", phase0)

            assert result.source_type == "EMAIL"
