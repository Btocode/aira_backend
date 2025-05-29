"""
AI service for paper analysis and processing.
"""
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

import openai
from openai import AsyncOpenAI
import anthropic
from anthropic import AsyncAnthropic

from app.core.config import settings
from app.core.app_logging import ai_logger, log_ai_request, log_error
from app.schemas.paper import PaperSummary, KeyInsight, PaperContribution


class AIService:
    """AI service for paper analysis and processing."""

    def __init__(self):
        """Initialize AI service with API clients."""
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

        if settings.anthropic_api_key:
            self.anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        else:
            self.anthropic_client = None

    async def summarize_paper(
        self,
        paper_content: str,
        paper_title: str,
        paper_authors: List[str] = None,
        model: str = "gpt-4-turbo"
    ) -> PaperSummary:
        """Generate comprehensive paper summary using AI."""

        ai_logger.info(f"Generating summary for paper: {paper_title[:50]}...")
        start_time = datetime.now()

        try:
            # Prepare content for AI
            content = self._prepare_paper_content(paper_content, paper_title, paper_authors)

            # Create prompt for summarization
            prompt = self._create_summarization_prompt(content)

            # Generate summary based on model
            if model.startswith("claude"):
                summary_data = await self._generate_claude_summary(prompt)
            else:
                summary_data = await self._generate_openai_summary(prompt, model)

            # Process response time
            response_time = (datetime.now() - start_time).total_seconds()
            log_ai_request("summarization", model, len(content), response_time)

            # Parse and validate summary
            summary = self._parse_summary_response(summary_data)

            ai_logger.info(f"Summary generated successfully for: {paper_title[:50]}...")
            return summary

        except Exception as e:
            ai_logger.error(f"Failed to generate summary for {paper_title}: {e}")
            log_error(e, {"paper_title": paper_title, "model": model})
            raise

    async def extract_key_insights(
        self,
        paper_content: str,
        paper_title: str,
        max_insights: int = 7
    ) -> List[KeyInsight]:
        """Extract key insights from paper."""

        ai_logger.info(f"Extracting insights for paper: {paper_title[:50]}...")
        start_time = datetime.now()

        try:
            # Prepare content
            content = paper_content[:settings.max_paper_length]

            prompt = f"""
            Extract {max_insights} key insights from this academic paper that would be valuable for researchers:

            Title: {paper_title}
            Content: {content}

            Return as a JSON array of objects with this structure:
            [
                {{
                    "insight": "The specific insight or finding",
                    "relevance_score": 0.9,
                    "section": "Results",
                    "page_number": 5
                }}
            ]

            Focus on:
            1. Novel findings and discoveries
            2. Methodological innovations
            3. Practical implications
            4. Theoretical contributions
            5. Limitations and future work
            6. Surprising or counterintuitive results
            7. Connections to other research areas

            Ensure insights are specific, actionable, and ranked by relevance (0.0-1.0).
            """

            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000
            )

            # Parse response
            content_text = response.choices[0].message.content
            insights_data = json.loads(content_text)

            # Convert to KeyInsight objects
            insights = [
                KeyInsight(
                    insight=item["insight"],
                    relevance_score=item.get("relevance_score", 0.5),
                    section=item.get("section"),
                    page_number=item.get("page_number")
                )
                for item in insights_data
            ]

            # Sort by relevance score
            insights.sort(key=lambda x: x.relevance_score, reverse=True)

            response_time = (datetime.now() - start_time).total_seconds()
            log_ai_request("insight_extraction", "gpt-4-turbo", len(content), response_time)

            ai_logger.info(f"Extracted {len(insights)} insights for: {paper_title[:50]}...")
            return insights

        except Exception as e:
            ai_logger.error(f"Failed to extract insights for {paper_title}: {e}")
            log_error(e, {"paper_title": paper_title})
            raise

    async def analyze_methodology(self, paper_content: str, paper_title: str) -> str:
        """Analyze paper methodology."""

        ai_logger.info(f"Analyzing methodology for: {paper_title[:50]}...")

        try:
            content = paper_content[:settings.max_paper_length]

            prompt = f"""
            Analyze the methodology section of this academic paper and provide a comprehensive summary:

            Title: {paper_title}
            Content: {content}

            Provide a detailed analysis covering:
            1. Research design and approach
            2. Data collection methods
            3. Sample size and selection criteria
            4. Analytical techniques used
            5. Tools and software employed
            6. Experimental setup (if applicable)
            7. Controls and variables
            8. Validation methods

            Focus on being specific and technical while remaining accessible.
            """

            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=800
            )

            methodology = response.choices[0].message.content

            ai_logger.info(f"Methodology analysis completed for: {paper_title[:50]}...")
            return methodology

        except Exception as e:
            ai_logger.error(f"Failed to analyze methodology for {paper_title}: {e}")
            log_error(e, {"paper_title": paper_title})
            raise

    async def identify_limitations(self, paper_content: str, paper_title: str) -> str:
        """Identify paper limitations."""

        ai_logger.info(f"Identifying limitations for: {paper_title[:50]}...")

        try:
            content = paper_content[:settings.max_paper_length]

            prompt = f"""
            Identify and analyze the limitations of this academic paper:

            Title: {paper_title}
            Content: {content}

            Analyze both explicitly stated limitations and potential implicit limitations:

            1. Methodological limitations
            2. Sample size or selection limitations
            3. Data quality or availability issues
            4. Scope and generalizability constraints
            5. Temporal limitations
            6. Technical or resource constraints
            7. Potential biases
            8. Areas not addressed

            Be constructive and specific in identifying limitations.
            """

            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=600
            )

            limitations = response.choices[0].message.content

            ai_logger.info(f"Limitations analysis completed for: {paper_title[:50]}...")
            return limitations

        except Exception as e:
            ai_logger.error(f"Failed to identify limitations for {paper_title}: {e}")
            log_error(e, {"paper_title": paper_title})
            raise

    async def extract_contributions(
        self,
        paper_content: str,
        paper_title: str
    ) -> List[PaperContribution]:
        """Extract paper contributions."""

        ai_logger.info(f"Extracting contributions for: {paper_title[:50]}...")

        try:
            content = paper_content[:settings.max_paper_length]

            prompt = f"""
            Extract the key contributions of this academic paper:

            Title: {paper_title}
            Content: {content}

            Return as a JSON array of objects with this structure:
            [
                {{
                    "contribution": "Specific contribution description",
                    "type": "theoretical/empirical/methodological/practical",
                    "significance": 0.8
                }}
            ]

            Types of contributions to look for:
            1. Theoretical: New theories, frameworks, models
            2. Empirical: New findings, evidence, data
            3. Methodological: New methods, tools, techniques
            4. Practical: Applications, implementations, solutions

            Rate significance from 0.0 (minor) to 1.0 (major breakthrough).
            """

            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=800
            )

            content_text = response.choices[0].message.content
            contributions_data = json.loads(content_text)

            contributions = [
                PaperContribution(
                    contribution=item["contribution"],
                    type=item["type"],
                    significance=item.get("significance", 0.5)
                )
                for item in contributions_data
            ]

            ai_logger.info(f"Extracted {len(contributions)} contributions for: {paper_title[:50]}...")
            return contributions

        except Exception as e:
            ai_logger.error(f"Failed to extract contributions for {paper_title}: {e}")
            log_error(e, {"paper_title": paper_title})
            raise

    async def generate_embeddings(self, text: str) -> List[float]:
        """Generate embeddings for semantic search."""

        try:
            # Truncate text if too long
            text = text[:8000]  # OpenAI embedding limit

            response = await self.openai_client.embeddings.create(
                model="text-embedding-3-large",
                input=text
            )

            embeddings = response.data[0].embedding

            ai_logger.info(f"Generated embeddings for text of length {len(text)}")
            return embeddings

        except Exception as e:
            ai_logger.error(f"Failed to generate embeddings: {e}")
            log_error(e, {"text_length": len(text)})
            raise

    async def batch_process_papers(
        self,
        papers_data: List[Dict[str, Any]],
        batch_size: int = None
    ) -> List[Dict[str, Any]]:
        """Process multiple papers in batches."""

        batch_size = batch_size or settings.ai_batch_size
        results = []

        ai_logger.info(f"Starting batch processing of {len(papers_data)} papers")

        for i in range(0, len(papers_data), batch_size):
            batch = papers_data[i:i + batch_size]

            # Process batch concurrently
            batch_tasks = [
                self._process_single_paper(paper_data)
                for paper_data in batch
            ]

            try:
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        ai_logger.error(f"Failed to process paper in batch: {result}")
                        results.append({"error": str(result), "paper_index": i + j})
                    else:
                        results.append(result)

            except Exception as e:
                ai_logger.error(f"Batch processing failed: {e}")
                log_error(e, {"batch_start": i, "batch_size": len(batch)})

        ai_logger.info(f"Batch processing completed: {len(results)} results")
        return results

    # Private helper methods
    def _prepare_paper_content(
        self,
        content: str,
        title: str,
        authors: List[str] = None
    ) -> str:
        """Prepare paper content for AI processing."""

        # Combine title, authors, and content
        prepared_content = f"Title: {title}\n\n"

        if authors:
            prepared_content += f"Authors: {', '.join(authors)}\n\n"

        prepared_content += content[:settings.max_paper_length]

        return prepared_content

    def _create_summarization_prompt(self, content: str) -> str:
        """Create prompt for paper summarization."""

        return f"""
        Analyze this academic paper and provide a comprehensive summary in JSON format:

        {content}

        Return a JSON object with this exact structure:
        {{
            "research_question": "What is the main research question or problem addressed?",
            "methodology": "Brief description of the research methods and approach used",
            "key_findings": ["Finding 1", "Finding 2", "Finding 3"],
            "limitations": ["Limitation 1", "Limitation 2"],
            "significance": "Why this research is important and its contribution to the field",
            "future_work": ["Future direction 1", "Future direction 2"],
            "confidence_score": 0.85
        }}

        Guidelines:
        - Be specific and accurate
        - Focus on the most important aspects
        - Limit key_findings to 3-5 items
        - Limit limitations to 2-4 items
        - Limit future_work to 2-3 items
        - Confidence score should reflect how well the paper is understood (0.0-1.0)
        """

    async def _generate_openai_summary(self, prompt: str, model: str) -> dict:
        """Generate summary using OpenAI."""

        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1200
        )

        content = response.choices[0].message.content
        return json.loads(content)

    async def _generate_claude_summary(self, prompt: str) -> dict:
        """Generate summary using Claude."""

        if not self.anthropic_client:
            raise ValueError("Anthropic client not initialized")

        response = await self.anthropic_client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1200,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text
        return json.loads(content)

    def _parse_summary_response(self, summary_data: dict) -> PaperSummary:
        """Parse and validate summary response."""

        return PaperSummary(
            research_question=summary_data.get("research_question", ""),
            methodology=summary_data.get("methodology", ""),
            key_findings=summary_data.get("key_findings", []),
            limitations=summary_data.get("limitations", []),
            significance=summary_data.get("significance", ""),
            future_work=summary_data.get("future_work", []),
            confidence_score=summary_data.get("confidence_score", 0.5)
        )

    async def _process_single_paper(self, paper_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single paper with AI."""

        try:
            title = paper_data.get("title", "")
            content = paper_data.get("content", "")
            authors = paper_data.get("authors", [])

            # Generate summary
            summary = await self.summarize_paper(content, title, authors)

            # Extract insights
            insights = await self.extract_key_insights(content, title)

            # Generate embeddings
            embeddings = await self.generate_embeddings(f"{title} {content}")

            return {
                "paper_id": paper_data.get("id"),
                "summary": summary.dict(),
                "insights": [insight.dict() for insight in insights],
                "embeddings": embeddings,
                "processing_status": "completed"
            }

        except Exception as e:
            return {
                "paper_id": paper_data.get("id"),
                "error": str(e),
                "processing_status": "failed"
            }


# Global AI service instance
ai_service = AIService()