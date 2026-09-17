"""Load and validate the `sources.yaml` corpus manifest."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl

MANIFEST_PATH = Path(__file__).with_name("sources.yaml")

Jurisdiction = Literal["AU", "VIC", "NSW", "QLD", "WA", "SA", "TAS", "NT", "ACT", "INT"]


class Source(BaseModel):
    """One page in the corpus."""

    id: str
    source_org: str
    url: HttpUrl
    jurisdiction: Jurisdiction
    licence: str
    secondary: bool = False
    topics: list[str] = Field(default_factory=list)
    enabled: bool = True
    terms_note: str = ""


class Manifest(BaseModel):
    """The whole corpus definition."""

    user_agent: str
    min_delay_s: float = 2.0
    sources: list[Source]

    @property
    def enabled_sources(self) -> list[Source]:
        """Sources that may be collected (terms and robots permit)."""
        return [s for s in self.sources if s.enabled]


def load_manifest(path: Path = MANIFEST_PATH) -> Manifest:
    """Parse the manifest and check that ids and URLs are unique."""
    manifest = Manifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    ids = [s.id for s in manifest.sources]
    urls = [str(s.url) for s in manifest.sources]
    dup_ids = {i for i in ids if ids.count(i) > 1}
    dup_urls = {u for u in urls if urls.count(u) > 1}
    if dup_ids or dup_urls:
        raise ValueError(f"Duplicate manifest entries: ids={dup_ids} urls={dup_urls}")
    return manifest
