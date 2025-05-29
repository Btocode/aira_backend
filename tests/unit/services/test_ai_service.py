"""
Unit tests for AI service.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
import json

from app.services.ai_service import AIService
from app.schemas.paper import PaperSummary, KeyInsight


class TestAIService:
    """Test AI service functionality."""

    @pytest.fixture
    def ai_service(self):
        """Create AI service instance for testing."""
        return AIService()

    @pytest.fixture
    def sample_paper_content(self):
        """Sample paper content for testing."""
        return """
        Title: Machine Learning in Academic Research

        Abstract: This paper explores the application of machine learning
        techniques in academic research. We present a comprehensive analysis
        of current trends and future opportunities.

        Introduction: Machine learning has become increasingly important...

        Methodology: We conducted a systematic review of literature...

        Results: Our analysis shows that ML can improve research efficiency...

        Conclusion: Machine learning offers significant potential for
        enhancing academic research processes.
        """

    @pytest.mark.asyncio
    async def test_summarize_paper_success(self, ai_service, sample_paper_content):
        """Test successful paper summarization."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "research_question": "How can ML improve academic research?",
            "methodology": "Systematic literature review",
            "key_findings": [
                "ML can automate literature reviews",
                "ML improves data analysis efficiency",
                "ML enables new research methodologies"
            ],
            "limitations": [
                "Limited to English language papers",
                "Focused on computer science domain"
            ],
            "significance": "Demonstrates the transformative potential of ML in research",
            "future_work": [
                "Expand to other academic domains",
                "Develop domain-specific ML tools"
            ],
            "confidence_score": 0.85
        })

        with patch.object(ai_service.openai_client.chat.completions, 'create',
                         new_callable=AsyncMock, return_value=mock_response):

            result = await ai_service.summarize_paper(
                sample_paper_content,
                "Machine Learning in Academic Research",
                ["John Doe", "Jane Smith"]
            )

            assert isinstance(result, PaperSummary)
            assert result.research_question == "How can ML improve academic research?"
            assert len(result.key_findings) == 3
            assert len(result.limitations) == 2
            assert result.confidence_score == 0.85

    @pytest.mark.asyncio
    async def test_summarize_paper_api_error(self, ai_service, sample_paper_content):
        """Test paper summarization with API error."""
        with patch.object(ai_service.openai_client.chat.completions, 'create',
                         side_effect=Exception("API Error")):

            with pytest.raises(Exception) as exc_info:
                await ai_service.summarize_paper(
                    sample_paper_content,
                    "Test Paper"
                )

            assert "API Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_key_insights_success(self, ai_service, sample_paper_content):
        """Test successful key insights extraction."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps([
            {
                "insight": "Machine learning can automate repetitive research tasks",
                "relevance_score": 0.9,
                "section": "Results",
                "page_number": 5
            },
            {
                "insight": "ML algorithms can identify patterns in large datasets",
                "relevance_score": 0.8,
                "section": "Discussion"
            }
        ])

        with patch.object(ai_service.openai_client.chat.completions, 'create',
                         new_callable=AsyncMock, return_value=mock_response):

            insights = await ai_service.extract_key_insights(
                sample_paper_content,
                "Machine Learning Paper"
            )

            assert len(insights) == 2
            assert all(isinstance(insight, KeyInsight) for insight in insights)
            assert insights[0].relevance_score == 0.9
            assert insights[0].section == "Results"
            assert insights[1].relevance_score == 0.8

    @pytest.mark.asyncio
    async def test_generate_embeddings_success(self, ai_service):
        """Test successful embeddings generation."""
        mock_response = Mock()
        mock_response.data = [Mock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3] * 512  # 1536 dimensions

        with patch.object(ai_service.openai_client.embeddings, 'create',
                         new_callable=AsyncMock, return_value=mock_response):

            embeddings = await ai_service.generate_embeddings("Test text for embeddings")

            assert len(embeddings) == 1536
            assert all(isinstance(val, float) for val in embeddings)

    @pytest.mark.asyncio
    async def test_generate_embeddings_text_truncation(self, ai_service):
        """Test embeddings generation with text truncation."""
        # Create very long text
        long_text = "This is a test sentence. " * 1000  # Much longer than 8000 chars

        mock_response = Mock()
        mock_response.data = [Mock()]
        mock_response.data[0].embedding = [0.1] * 1536

        with patch.object(ai_service.openai_client.embeddings, 'create',
                         new_callable=AsyncMock, return_value=mock_response) as mock_create:

            await ai_service.generate_embeddings(long_text)

            # Check that the text was truncated
            call_args = mock_create.call_args
            input_text = call_args.kwargs['input']
            assert len(input_text) <= 8000

    @pytest.mark.asyncio
    async def test_analyze_methodology_success(self, ai_service, sample_paper_content):
        """Test successful methodology analysis."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = """
        The research methodology employed in this study consists of:

        1. Research Design: Systematic literature review approach
        2. Data Collection: Comprehensive search across academic databases
        3. Sample Selection: Papers published between 2020-2024
        4. Analytical Techniques: Thematic analysis and statistical correlation
        5. Tools: Python for data processing, R for statistical analysis
        """

        with patch.object(ai_service.openai_client.chat.completions, 'create',
                         new_callable=AsyncMock, return_value=mock_response):

            methodology = await ai_service.analyze_methodology(
                sample_paper_content,
                "Test Paper"
            )

            assert isinstance(methodology, str)
            assert "systematic literature review" in methodology.lower()
            assert "data collection" in methodology.lower()

    @pytest.mark.asyncio
    async def test_identify_limitations_success(self, ai_service, sample_paper_content):
        """Test successful limitations identification."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = """
        The study has several limitations:

        1. Scope limitations: Only English-language papers were included
        2. Temporal constraints: Limited to recent publications (2020-2024)
        3. Database coverage: Only searched three academic databases
        4. Methodological limitations: Subjective interpretation in thematic analysis
        """

        with patch.object(ai_service.openai_client.chat.completions, 'create',
                         new_callable=AsyncMock, return_value=mock_response):

            limitations = await ai_service.identify_limitations(
                sample_paper_content,
                "Test Paper"
            )

            assert isinstance(limitations, str)
            assert "limitations" in limitations.lower()
            assert "scope" in limitations.lower()

    @pytest.mark.asyncio
    async def test_batch_process_papers_success(self, ai_service):
        """Test successful batch processing of papers."""
        papers_data = [
            {
                "id": "paper1",
                "title": "Paper 1",
                "content": "Content 1",
                "authors": ["Author 1"]
            },
            {
                "id": "paper2",
                "title": "Paper 2",
                "content": "Content 2",
                "authors": ["Author 2"]
            }
        ]

        # Mock the _process_single_paper method
        with patch.object(ai_service, '_process_single_paper',
                         new_callable=AsyncMock) as mock_process:

            mock_process.side_effect = [
                {
                    "paper_id": "paper1",
                    "summary": {"research_question": "Question 1"},
                    "processing_status": "completed"
                },
                {
                    "paper_id": "paper2",
                    "summary": {"research_question": "Question 2"},
                    "processing_status": "completed"
                }
            ]

            results = await ai_service.batch_process_papers(papers_data, batch_size=2)

            assert len(results) == 2
            assert all(result["processing_status"] == "completed" for result in results)

    @pytest.mark.asyncio
    async def test_batch_process_papers_with_errors(self, ai_service):
        """Test batch processing with some failures."""
        papers_data = [
            {"id": "paper1", "title": "Paper 1", "content": "Content 1"},
            {"id": "paper2", "title": "Paper 2", "content": "Content 2"}
        ]

        with patch.object(ai_service, '_process_single_paper',
                         new_callable=AsyncMock) as mock_process:

            # First paper succeeds, second fails
            mock_process.side_effect = [
                {"paper_id": "paper1", "processing_status": "completed"},
                Exception("Processing failed")
            ]

            results = await ai_service.batch_process_papers(papers_data)

            assert len(results) == 2
            assert results[0]["processing_status"] == "completed"
            assert "error" in results[1]

    def test_prepare_paper_content(self, ai_service):
        """Test paper content preparation."""
        content = ai_service._prepare_paper_content(
            "This is the paper content.",
            "Paper Title",
            ["Author 1", "Author 2"]
        )

        assert "Title: Paper Title" in content
        assert "Authors: Author 1, Author 2" in content
        assert "This is the paper content." in content

    def test_create_summarization_prompt(self, ai_service):
        """Test summarization prompt creation."""
        content = "Sample paper content for testing."
        prompt = ai_service._create_summarization_prompt(content)

        assert "JSON object" in prompt
        assert "research_question" in prompt
        assert "methodology" in prompt
        assert "key_findings" in prompt
        assert content in prompt

    def test_parse_summary_response(self, ai_service):
        """Test summary response parsing."""
        summary_data = {
            "research_question": "Test question?",
            "methodology": "Test methodology",
            "key_findings": ["Finding 1", "Finding 2"],
            "limitations": ["Limitation 1"],
            "significance": "Test significance",
            "future_work": ["Future work 1"],
            "confidence_score": 0.85
        }

        summary = ai_service._parse_summary_response(summary_data)

        assert isinstance(summary, PaperSummary)
        assert summary.research_question == "Test question?"
        assert len(summary.key_findings) == 2
        assert summary.confidence_score == 0.85


class TestAIServiceEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def ai_service(self):
        return AIService()

    @pytest.mark.asyncio
    async def test_empty_content_handling(self, ai_service):
        """Test handling of empty content."""
        with pytest.raises(Exception):
            await ai_service.summarize_paper("", "Empty Paper")

    @pytest.mark.asyncio
    async def test_very_long_content_truncation(self, ai_service):
        """Test handling of very long content."""
        from app.core.config import settings

        # Create content longer than max_paper_length
        long_content = "A" * (settings.max_paper_length + 1000)

        # Mock to capture the actual content sent to AI
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "research_question": "Test",
            "methodology": "Test",
            "key_findings": ["Test"],
            "limitations": ["Test"],
            "significance": "Test",
            "future_work": ["Test"],
            "confidence_score": 0.5
        })

        with patch.object(ai_service.openai_client.chat.completions, 'create',
                         new_callable=AsyncMock, return_value=mock_response) as mock_create:

            await ai_service.summarize_paper(long_content, "Long Paper")

            # Verify content was truncated
            call_args = mock_create.call_args
            sent_content = call_args.kwargs['messages'][0]['content']
            assert len(sent_content) <= settings.max_paper_length + 200  # Some buffer for formatting

    @pytest.mark.asyncio
    async def test_invalid_json_response_handling(self, ai_service):
        """Test handling of invalid JSON response from AI."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Invalid JSON response"

        with patch.object(ai_service.openai_client.chat.completions, 'create',
                         new_callable=AsyncMock, return_value=mock_response):

            with pytest.raises(Exception):
                await ai_service.summarize_paper("Test content", "Test Paper")