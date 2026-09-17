"""HTML → clean markdown with page title."""

from __future__ import annotations

import re

_TITLE_SUFFIX = re.compile(
    r"\s*[|\-–—]\s*(healthdirect|Better Health Channel|NSW Health|Queensland Health|"
    r"Australian Dental Association|ADA|AIHW|Australian Institute of Health and Welfare|"
    r"World Health Organization|WHO|Dental Health Services.*|SA Dental.*|Health\.vic)\s*$",
    re.IGNORECASE,
)

_BOILERPLATE = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^\s*(share|print|email)( this page)?\s*$",
        r"^\s*was this (page|article) helpful\??.*$",
        r"^\s*last (reviewed|updated)[: ].*$",
        r"^\s*back to top\s*$",
        r"^\s*skip to (main )?content\s*$",
    )
]


#: Site-specific non-article blocks removed before extraction (feedback widgets, share forms).
_SITE_JUNK = re.compile(
    r"<(div|section|aside)\b[^>]*(class|id)=\"[^\"]*(share-by-email|feedback|page-rating|"
    r"was-this-helpful|social-share|testimonial|you-said)[^\"]*\"[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)


def clean_title(title: str) -> str:
    """Strip publisher suffixes like ' | healthdirect'."""
    return _TITLE_SUFFIX.sub("", title.strip()).strip()


def extract(html: str, url: str) -> tuple[str, str]:
    """Return (title, markdown body) with navigation and boilerplate removed."""
    import trafilatura

    meta = trafilatura.extract_metadata(html)
    title = clean_title(meta.title) if meta and meta.title else url
    html = _SITE_JUNK.sub("", html)

    def run(doc: str, precision: bool) -> str:
        return (
            trafilatura.extract(
                doc,
                url=url,
                output_format="markdown",
                include_formatting=True,
                include_links=False,
                include_images=False,
                include_comments=False,
                include_tables=True,
                favor_precision=precision,
                favor_recall=not precision,
            )
            or ""
        )

    body = run(html, precision=True)
    if len(body.split()) < 100:
        # Some CMSs (e.g. NSW Health SharePoint) wrap the whole page in <form>, which
        # trafilatura discards. Unwrap forms and retry with recall-oriented extraction.
        body = run(re.sub(r"</?form\b[^>]*>", "", html, flags=re.IGNORECASE), precision=False)
    return title, strip_boilerplate(body)


def strip_boilerplate(markdown: str) -> str:
    """Drop share/print/feedback lines and collapse blank runs."""
    lines = [ln for ln in markdown.splitlines() if not any(p.match(ln) for p in _BOILERPLATE)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
