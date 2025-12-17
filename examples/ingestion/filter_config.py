"""
Content filtering configuration models for selective document ingestion.

This module defines Pydantic models for configuring content exclusion rules
when ingesting documents. Supports filtering by section headers, page ranges,
and text patterns.
"""

from typing import Optional

from pydantic import BaseModel, Field


class SubsectionExclusion(BaseModel):
    """
    Configuration for excluding a specific subsection.

    Attributes:
        title: Subsection title/heading to exclude
        page: Optional page number where the subsection appears
        pattern: Optional regex pattern to match subsection content
    """

    title: str = Field(..., description="Subsection title to exclude")
    page: Optional[int] = Field(None, description="Page number (if known)")
    pattern: Optional[str] = Field(None, description="Regex pattern to match content")


class FilterConfig(BaseModel):
    """
    Configuration for document content filtering.

    Defines exclusion rules for sections, pages, and patterns that should be
    removed during document ingestion. Used for textbooks where certain
    sections (practice problems, exercises) should not be included in the
    learning corpus.

    Attributes:
        subject: Subject area (e.g., "biology", "chemistry")
        book: Full book title
        authors: List of book authors
        exclude_sections: Section headers to exclude completely
        exclude_subsections: Subsections with specific titles/pages to exclude
        exclude_pages: Individual page numbers to exclude
        exclude_patterns: Regex patterns to match and exclude content
        case_sensitive: Whether section matching is case-sensitive
    """

    subject: str = Field(..., description="Subject area (e.g., biology, chemistry)")
    book: str = Field(..., description="Full book title")
    authors: list[str] = Field(default_factory=list, description="Book authors")
    exclude_sections: list[str] = Field(
        default_factory=list,
        description="Section headers to exclude (e.g., 'Teme și aplicații')",
    )
    exclude_subsections: list[SubsectionExclusion] = Field(
        default_factory=list,
        description="Specific subsections to exclude",
    )
    exclude_pages: list[int] = Field(
        default_factory=list, description="Page numbers to exclude"
    )
    exclude_patterns: list[str] = Field(
        default_factory=list,
        description="Regex patterns to match and exclude content blocks",
    )
    case_sensitive: bool = Field(
        default=False, description="Whether section header matching is case-sensitive"
    )

    def has_exclusions(self) -> bool:
        """
        Check if any exclusion rules are defined.

        Returns:
            True if at least one exclusion rule is defined
        """
        return bool(
            self.exclude_sections
            or self.exclude_subsections
            or self.exclude_pages
            or self.exclude_patterns
        )


class FilterMetadata(BaseModel):
    """
    Metadata tracking what content was filtered from a document.

    Attributes:
        sections_removed: List of section titles that were excluded
        pages_removed: List of page numbers that were excluded
        blocks_removed: Total number of document blocks removed
        filter_config_used: Name/identifier of filter config applied
    """

    sections_removed: list[str] = Field(
        default_factory=list, description="Section titles excluded"
    )
    pages_removed: list[int] = Field(
        default_factory=list, description="Page numbers excluded"
    )
    blocks_removed: int = Field(default=0, description="Total blocks removed")
    filter_config_used: Optional[str] = Field(
        None, description="Filter config identifier"
    )
