"""
Content filtering for DoclingDocument structures.

This module provides filtering capabilities to selectively remove content from
DoclingDocument objects based on section headers, page ranges, and text patterns.
Used for processing educational materials where certain sections (e.g., practice
problems, exercises) should not be included in the RAG corpus.
"""

import re
import logging
from typing import Optional
from copy import deepcopy

from docling_core.types.doc import DoclingDocument, DocItemLabel

from examples.ingestion.filter_config import FilterConfig, FilterMetadata

logger = logging.getLogger(__name__)


class ContentFilter:
    """
    Filter content from DoclingDocument based on exclusion rules.

    This filter works directly with DoclingDocument structure to remove:
    - Sections by header name (e.g., "Teme și aplicații", "Lucrări practice")
    - Content from specific page ranges
    - Content matching regex patterns

    The filtered document maintains its structure and can be passed to
    HybridChunker for proper contextualized chunking.
    """

    def __init__(self, config: FilterConfig):
        """
        Initialize content filter.

        Args:
            config: Filter configuration with exclusion rules
        """
        self.config = config
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        self.compiled_patterns = [
            re.compile(pattern, flags=0 if self.config.case_sensitive else re.IGNORECASE)
            for pattern in self.config.exclude_patterns
        ]

    async def filter_document(
        self, docling_doc: DoclingDocument, file_path: str
    ) -> tuple[DoclingDocument, FilterMetadata]:
        """
        Filter DoclingDocument based on configuration rules.

        Args:
            docling_doc: Document to filter
            file_path: Source file path (for logging)

        Returns:
            Tuple of (filtered_document, filter_metadata)
        """
        if not self.config.has_exclusions():
            logger.info(f"No exclusions configured, skipping filtering for {file_path}")
            return (docling_doc, FilterMetadata())

        logger.info(f"Applying content filter to {file_path}")

        # Work with a copy to avoid mutating original
        filtered_doc = deepcopy(docling_doc)

        # Track filtering operations
        metadata = FilterMetadata(
            filter_config_used=f"{self.config.subject}:{self.config.book}"
        )

        # Filter document body by removing matching items
        if hasattr(filtered_doc, "body") and hasattr(filtered_doc.body, "items"):
            original_count = len(filtered_doc.body.items)

            # Track which sections we're currently inside (for multi-block sections)
            in_excluded_section = False
            current_section_title = None

            filtered_items = []

            for item in filtered_doc.body.items:
                # Check if this is a heading
                is_heading = (
                    hasattr(item, "label") and item.label == DocItemLabel.SECTION_HEADER
                )

                if is_heading:
                    # Check if this heading matches an excluded section
                    heading_text = self._extract_text(item)
                    if self._should_exclude_section(heading_text):
                        in_excluded_section = True
                        current_section_title = heading_text
                        metadata.sections_removed.append(heading_text)
                        logger.debug(
                            f"Excluding section: {heading_text} from {file_path}"
                        )
                        continue  # Skip this heading
                    else:
                        # New section that's not excluded - reset flag
                        in_excluded_section = False
                        current_section_title = None

                # If we're in an excluded section, skip all content until next heading
                if in_excluded_section:
                    continue

                # Check page-based exclusion
                if self._should_exclude_by_page(item):
                    page_num = self._extract_page_number(item)
                    if page_num and page_num not in metadata.pages_removed:
                        metadata.pages_removed.append(page_num)
                        logger.debug(f"Excluding content from page {page_num}")
                    continue

                # Check pattern-based exclusion
                if self._should_exclude_by_pattern(item):
                    logger.debug(
                        f"Excluding content matching pattern: {self._extract_text(item)[:50]}..."
                    )
                    continue

                # Check subsection-specific exclusion
                if self._should_exclude_subsection(item):
                    subsection_text = self._extract_text(item)
                    if subsection_text not in metadata.sections_removed:
                        metadata.sections_removed.append(subsection_text)
                    logger.debug(f"Excluding subsection: {subsection_text}")
                    continue

                # Item passed all filters - keep it
                filtered_items.append(item)

            # Update document with filtered items
            filtered_doc.body.items = filtered_items

            metadata.blocks_removed = original_count - len(filtered_items)
            logger.info(
                f"Filtered {metadata.blocks_removed} blocks from {file_path} "
                f"({len(filtered_items)}/{original_count} blocks remaining)"
            )

        return (filtered_doc, metadata)

    def _should_exclude_section(self, heading_text: str) -> bool:
        """
        Check if section header matches exclusion rules.

        Args:
            heading_text: Section heading text

        Returns:
            True if section should be excluded
        """
        if not heading_text:
            return False

        for excluded_section in self.config.exclude_sections:
            if self.config.case_sensitive:
                if heading_text.strip() == excluded_section:
                    return True
            else:
                if heading_text.strip().lower() == excluded_section.lower():
                    return True

        return False

    def _should_exclude_by_page(self, item) -> bool:
        """
        Check if item is on an excluded page.

        Args:
            item: Document item to check

        Returns:
            True if item is on an excluded page
        """
        if not self.config.exclude_pages:
            return False

        page_num = self._extract_page_number(item)
        return page_num in self.config.exclude_pages if page_num else False

    def _should_exclude_by_pattern(self, item) -> bool:
        """
        Check if item content matches any exclusion patterns.

        Args:
            item: Document item to check

        Returns:
            True if item matches an exclusion pattern
        """
        if not self.compiled_patterns:
            return False

        text = self._extract_text(item)
        if not text:
            return False

        for pattern in self.compiled_patterns:
            if pattern.search(text):
                return True

        return False

    def _should_exclude_subsection(self, item) -> bool:
        """
        Check if item matches a specific subsection exclusion rule.

        Args:
            item: Document item to check

        Returns:
            True if item is an excluded subsection
        """
        if not self.config.exclude_subsections:
            return False

        text = self._extract_text(item)
        page_num = self._extract_page_number(item)

        for subsection in self.config.exclude_subsections:
            # Match by title
            if self.config.case_sensitive:
                title_match = text and text.strip() == subsection.title
            else:
                title_match = text and text.strip().lower() == subsection.title.lower()

            # If page is specified, must also match page
            if subsection.page:
                if title_match and page_num == subsection.page:
                    return True
            elif title_match:
                return True

            # Check pattern if specified
            if subsection.pattern and text:
                pattern = re.compile(
                    subsection.pattern,
                    flags=0 if self.config.case_sensitive else re.IGNORECASE,
                )
                if pattern.search(text):
                    return True

        return False

    def _extract_text(self, item) -> Optional[str]:
        """
        Extract text content from a document item.

        Args:
            item: Document item

        Returns:
            Extracted text or None
        """
        if hasattr(item, "text"):
            return item.text

        # Try alternate text extraction methods
        if hasattr(item, "get_text"):
            return item.get_text()

        return None

    def _extract_page_number(self, item) -> Optional[int]:
        """
        Extract page number from a document item.

        Args:
            item: Document item

        Returns:
            Page number or None
        """
        # Check prov (provenance) metadata which typically has page info
        if hasattr(item, "prov") and item.prov:
            for prov_item in item.prov:
                if hasattr(prov_item, "page_no"):
                    return prov_item.page_no

        # Fallback: check metadata
        if hasattr(item, "meta") and isinstance(item.meta, dict):
            if "page" in item.meta:
                return item.meta["page"]
            if "page_no" in item.meta:
                return item.meta["page_no"]

        return None


def create_filter(config: FilterConfig) -> ContentFilter:
    """
    Create ContentFilter instance.

    Args:
        config: Filter configuration

    Returns:
        ContentFilter instance
    """
    return ContentFilter(config)
