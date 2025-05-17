from __future__ import annotations

"""Schema definitions for the Smart Crawler pipeline.

These models are consumed by:
  • `smart_crawler.py`  – parses raw HTML and emits `PageContent` objects
  • `prompt_agent/lovable_prompter.py` – reads the JSON files written by the
    crawler and converts them into prompt text for Lovable.

Why **Pydantic**?
- Validation & parsing super‑powers.
- Built‑in `.model_dump()` / `.model_validate()` for seamless JSON ↔ object
  transformations.
"""

from typing import List, Optional
from pydantic import BaseModel, HttpUrl, Field

# ---------------------------------------------------------------------------
# Low‑level building blocks
# ---------------------------------------------------------------------------

class ImageRef(BaseModel):
    """Reference to an image asset used in a section."""

    src: HttpUrl = Field(..., description="Absolute image URL")
    alt: Optional[str] = Field(None, description="Alt text for accessibility")


class Section(BaseModel):
    """A logical content block inside a page (hero, features, faq, etc.)."""

    id: str = Field(..., description="Slug‑style unique identifier, e.g. 'hero'")
    heading: Optional[str] = Field(None, description="Headline or title of the section")
    body: str = Field(..., description="Raw text (Markdown allowed)")
    images: List[ImageRef] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top‑level page container
# ---------------------------------------------------------------------------

class PageContent(BaseModel):
    """Fully‑structured representation of a single web page's content."""

    page: str = Field(..., description="Route slug, e.g. 'homepage' or 'services'")
    url: HttpUrl = Field(..., description="Canonical URL for this page")
    sections: List[Section] = Field(default_factory=list)

    # Convenience helpers ----------------------------------------------------
    def add_section(self, **kwargs) -> None:
        self.sections.append(Section(**kwargs))

    def to_json(self, indent: int | None = 2) -> str:  # helper for writing files
        return self.model_dump(mode="json", by_alias=True, indent=indent)  # type: ignore[arg-type]


__all__ = [
    "ImageRef",
    "Section",
    "PageContent",
]
