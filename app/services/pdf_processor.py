"""
PDF processing service for extracting text and metadata from academic papers.
"""
import io
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

import httpx
import fitz  # PyMuPDF
from PyPDF2 import PdfReader

from app.core.config import settings
from app.core.app_logging import paper_logger, log_error


class PDFProcessor:
    """Service for processing PDF documents."""

    def __init__(self):
        """Initialize PDF processor."""
        self.http_client = httpx.AsyncClient(
            timeout=60.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )

    async def extract_text_from_url(self, pdf_url: str) -> Optional[str]:
        """Extract text from PDF URL."""

        paper_logger.info(f"Extracting text from PDF: {pdf_url}")

        try:
            # Download PDF
            pdf_content = await self._download_pdf(pdf_url)

            if not pdf_content:
                return None

            # Extract text
            text = await self._extract_text_from_bytes(pdf_content)

            if text:
                paper_logger.info(f"Successfully extracted {len(text)} characters from PDF")
                return text
            else:
                paper_logger.warning(f"No text extracted from PDF: {pdf_url}")
                return None

        except Exception as e:
            paper_logger.error(f"Failed to extract text from PDF {pdf_url}: {e}")
            log_error(e, {"pdf_url": pdf_url})
            return None

    async def extract_metadata_from_url(self, pdf_url: str) -> Dict[str, Any]:
        """Extract metadata from PDF URL."""

        paper_logger.info(f"Extracting metadata from PDF: {pdf_url}")

        try:
            # Download PDF
            pdf_content = await self._download_pdf(pdf_url)

            if not pdf_content:
                return {}

            # Extract metadata
            metadata = await self._extract_metadata_from_bytes(pdf_content)

            paper_logger.info(f"Successfully extracted metadata from PDF")
            return metadata

        except Exception as e:
            paper_logger.error(f"Failed to extract metadata from PDF {pdf_url}: {e}")
            log_error(e, {"pdf_url": pdf_url})
            return {}

    async def process_uploaded_pdf(self, pdf_content: bytes) -> Dict[str, Any]:
        """Process uploaded PDF file."""

        paper_logger.info("Processing uploaded PDF file")

        try:
            # Extract text
            text = await self._extract_text_from_bytes(pdf_content)

            # Extract metadata
            metadata = await self._extract_metadata_from_bytes(pdf_content)

            # Analyze paper structure
            structure = await self._analyze_paper_structure(text)

            result = {
                "text": text,
                "metadata": metadata,
                "structure": structure,
                "length": len(text) if text else 0
            }

            paper_logger.info(f"Successfully processed uploaded PDF: {len(text)} characters")
            return result

        except Exception as e:
            paper_logger.error(f"Failed to process uploaded PDF: {e}")
            log_error(e, {"content_length": len(pdf_content)})
            raise

    async def _download_pdf(self, pdf_url: str) -> Optional[bytes]:
        """Download PDF from URL."""

        try:
            async with self.http_client as client:
                response = await client.get(pdf_url)
                response.raise_for_status()

                # Check content type
                content_type = response.headers.get("content-type", "").lower()
                if "pdf" not in content_type and not pdf_url.endswith('.pdf'):
                    paper_logger.warning(f"URL may not be a PDF: {content_type}")

                # Check file size
                content_length = len(response.content)
                if content_length > settings.upload_max_size:
                    raise ValueError(f"PDF too large: {content_length} bytes")

                paper_logger.info(f"Downloaded PDF: {content_length} bytes")
                return response.content

        except httpx.TimeoutException:
            paper_logger.error(f"Timeout downloading PDF: {pdf_url}")
            return None
        except httpx.HTTPStatusError as e:
            paper_logger.error(f"HTTP error downloading PDF {pdf_url}: {e.response.status_code}")
            return None
        except Exception as e:
            paper_logger.error(f"Error downloading PDF {pdf_url}: {e}")
            return None

    async def _extract_text_from_bytes(self, pdf_content: bytes) -> Optional[str]:
        """Extract text from PDF bytes using multiple methods."""

        # Try PyMuPDF first (better for academic papers)
        text = await self._extract_text_pymupdf(pdf_content)

        if not text or len(text.strip()) < 100:
            # Fallback to PyPDF2
            paper_logger.info("PyMuPDF extraction failed, trying PyPDF2")
            text = await self._extract_text_pypdf2(pdf_content)

        if text:
            # Clean and normalize text
            text = self._clean_extracted_text(text)

            # Limit text length
            if len(text) > settings.max_paper_length:
                text = text[:settings.max_paper_length]
                paper_logger.info(f"Text truncated to {settings.max_paper_length} characters")

        return text

    async def _extract_text_pymupdf(self, pdf_content: bytes) -> Optional[str]:
        """Extract text using PyMuPDF."""

        try:
            # Open PDF from bytes
            pdf_document = fitz.open(stream=pdf_content, filetype="pdf")

            text_blocks = []

            for page_num in range(pdf_document.page_count):
                page = pdf_document.load_page(page_num)

                # Extract text with layout preservation
                text = page.get_text("text")

                if text.strip():
                    text_blocks.append(f"--- Page {page_num + 1} ---\n{text}")

            pdf_document.close()

            if text_blocks:
                return "\n\n".join(text_blocks)
            else:
                return None

        except Exception as e:
            paper_logger.error(f"PyMuPDF extraction failed: {e}")
            return None

    async def _extract_text_pypdf2(self, pdf_content: bytes) -> Optional[str]:
        """Extract text using PyPDF2."""

        try:
            pdf_reader = PdfReader(io.BytesIO(pdf_content))

            text_blocks = []

            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()

                if text.strip():
                    text_blocks.append(f"--- Page {page_num + 1} ---\n{text}")

            if text_blocks:
                return "\n\n".join(text_blocks)
            else:
                return None

        except Exception as e:
            paper_logger.error(f"PyPDF2 extraction failed: {e}")
            return None

    def _clean_extracted_text(self, text: str) -> str:
        """Clean and normalize extracted text."""

        if not text:
            return text

        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        # Fix common OCR errors in academic papers
        text = re.sub(r'(?<=\w)- (?=\w)', '', text)  # Remove hyphenation
        text = re.sub(r'(\w)\s+([.,;:!?])', r'\1\2', text)  # Fix punctuation spacing

        # Remove page numbers and headers/footers (simple approach)
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            line = line.strip()

            # Skip likely page numbers
            if re.match(r'^\d+$', line):
                continue

            # Skip short lines that are likely headers/footers
            if len(line) < 10 and (
                'page' in line.lower() or
                'vol' in line.lower() or
                re.match(r'^[IVX]+$', line)
            ):
                continue

            cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    async def _extract_metadata_from_bytes(self, pdf_content: bytes) -> Dict[str, Any]:
        """Extract metadata from PDF bytes."""

        metadata = {}

        try:
            # Try PyMuPDF for metadata
            pdf_document = fitz.open(stream=pdf_content, filetype="pdf")

            pdf_metadata = pdf_document.metadata

            if pdf_metadata:
                metadata.update({
                    "title": pdf_metadata.get("title", ""),
                    "author": pdf_metadata.get("author", ""),
                    "subject": pdf_metadata.get("subject", ""),
                    "creator": pdf_metadata.get("creator", ""),
                    "producer": pdf_metadata.get("producer", ""),
                    "creation_date": pdf_metadata.get("creationDate", ""),
                    "modification_date": pdf_metadata.get("modDate", "")
                })

            # Get page count
            metadata["page_count"] = pdf_document.page_count

            # Try to extract title and authors from first page
            if pdf_document.page_count > 0:
                first_page = pdf_document.load_page(0)
                first_page_text = first_page.get_text("text")

                paper_info = self._extract_paper_info_from_text(first_page_text)
                metadata.update(paper_info)

            pdf_document.close()

        except Exception as e:
            paper_logger.error(f"Metadata extraction failed: {e}")

        # Clean up metadata
        metadata = self._clean_metadata(metadata)

        return metadata

    def _extract_paper_info_from_text(self, text: str) -> Dict[str, Any]:
        """Extract paper information from text (title, authors, abstract)."""

        info = {}

        if not text:
            return info

        lines = [line.strip() for line in text.split('\n') if line.strip()]

        if not lines:
            return info

        # Try to identify title (usually first non-empty line or longest line in first few lines)
        potential_titles = lines[:5]  # Look at first 5 lines

        # Find the longest line as potential title
        if potential_titles:
            title_line = max(potential_titles, key=len)

            # Basic validation for title
            if len(title_line) > 10 and len(title_line) < 200:
                info["title"] = title_line

        # Try to identify authors (look for common patterns)
        authors = []

        for i, line in enumerate(lines[:10]):  # Check first 10 lines
            # Look for author patterns
            if self._looks_like_author_line(line):
                authors.extend(self._parse_author_line(line))

        if authors:
            info["authors"] = [{"name": author} for author in authors]

        # Try to identify abstract
        abstract_start = -1
        for i, line in enumerate(lines):
            if line.lower().startswith('abstract'):
                abstract_start = i
                break

        if abstract_start != -1 and abstract_start + 1 < len(lines):
            # Extract abstract (next few lines after "Abstract")
            abstract_lines = []
            for i in range(abstract_start + 1, min(abstract_start + 10, len(lines))):
                line = lines[i]
                if self._looks_like_section_header(line):
                    break
                abstract_lines.append(line)

            if abstract_lines:
                info["abstract"] = " ".join(abstract_lines)

        return info

    def _looks_like_author_line(self, line: str) -> bool:
        """Check if line looks like it contains author names."""

        # Common patterns for author lines
        patterns = [
            r'^[A-Z][a-z]+ [A-Z][a-z]+',  # First Last
            r'^[A-Z]\. [A-Z][a-z]+',      # F. Last
            r'[A-Z][a-z]+.*@.*\.',         # Contains email
            r'^.*\s+and\s+.*$',            # Contains "and"
        ]

        for pattern in patterns:
            if re.search(pattern, line):
                return True

        return False

    def _parse_author_line(self, line: str) -> List[str]:
        """Parse author names from line."""

        authors = []

        # Split by common delimiters
        delimiters = [',', ' and ', ' & ', ';']

        parts = [line]
        for delimiter in delimiters:
            new_parts = []
            for part in parts:
                new_parts.extend(part.split(delimiter))
            parts = new_parts

        for part in parts:
            part = part.strip()

            # Remove emails and affiliations
            part = re.sub(r'\s*\([^)]*\)', '', part)  # Remove parentheses
            part = re.sub(r'\s*\{[^}]*\}', '', part)  # Remove braces
            part = re.sub(r'\s*<[^>]*>', '', part)   # Remove angle brackets
            part = re.sub(r'\s*\[[^\]]*\]', '', part) # Remove square brackets

            part = part.strip()

            # Basic validation
            if len(part) > 2 and len(part) < 50 and ' ' in part:
                authors.append(part)

        return authors

    def _looks_like_section_header(self, line: str) -> bool:
        """Check if line looks like a section header."""

        headers = [
            'introduction', 'background', 'methodology', 'methods',
            'results', 'discussion', 'conclusion', 'references',
            'acknowledgments', 'appendix', 'keywords'
        ]

        line_lower = line.lower().strip()

        # Check for exact matches or numbered sections
        for header in headers:
            if line_lower == header or line_lower.startswith(f'{header}:'):
                return True

        # Check for numbered sections (1. Introduction, etc.)
        if re.match(r'^\d+[\.\s]+[a-zA-Z]', line):
            return True

        return False

    def _clean_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and normalize metadata."""

        cleaned = {}

        for key, value in metadata.items():
            if value is None:
                continue

            if isinstance(value, str):
                value = value.strip()
                if not value:
                    continue

            cleaned[key] = value

        # Convert author string to list if needed
        if "author" in cleaned and isinstance(cleaned["author"], str):
            authors = self._parse_author_line(cleaned["author"])
            if authors:
                cleaned["authors"] = [{"name": author} for author in authors]
            del cleaned["author"]

        return cleaned

    async def _analyze_paper_structure(self, text: str) -> Dict[str, Any]:
        """Analyze paper structure and extract sections."""

        if not text:
            return {}

        structure = {
            "sections": [],
            "has_abstract": False,
            "has_introduction": False,
            "has_conclusion": False,
            "has_references": False,
            "estimated_pages": 0
        }

        try:
            # Split into lines
            lines = text.split('\n')

            # Estimate page count
            page_markers = [line for line in lines if line.strip().startswith('---')]
            structure["estimated_pages"] = len(page_markers)

            # Find sections
            sections = []
            current_section = None

            for line in lines:
                line = line.strip()

                if self._looks_like_section_header(line):
                    if current_section:
                        sections.append(current_section)

                    current_section = {
                        "title": line,
                        "content": []
                    }

                    # Check for specific sections
                    line_lower = line.lower()
                    if "abstract" in line_lower:
                        structure["has_abstract"] = True
                    elif "introduction" in line_lower:
                        structure["has_introduction"] = True
                    elif "conclusion" in line_lower:
                        structure["has_conclusion"] = True
                    elif "references" in line_lower or "bibliography" in line_lower:
                        structure["has_references"] = True

                elif current_section and line:
                    current_section["content"].append(line)

            # Add last section
            if current_section:
                sections.append(current_section)

            structure["sections"] = sections

        except Exception as e:
            paper_logger.error(f"Paper structure analysis failed: {e}")

        return structure


# Global PDF processor instance
pdf_processor = PDFProcessor()