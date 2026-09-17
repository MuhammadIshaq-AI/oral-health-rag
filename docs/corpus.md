# Corpus: sources, permissions and provenance

The primary index contains **Australian public-guidance pages only**; WHO fact
sheets are included as clearly-labelled secondary, non-Australian material.

Nothing scraped is committed. The repository contains the manifest
(`ingest/sources.yaml`) and the pipeline; running `make ingest` reproduces the
corpus locally into `data/` (git-ignored).

## What is indexed

Run `python -m ingest.cli stats` for the live table. As of the corpus build
described in the README: 38 pages / 145 chunks from healthdirect Australia, NSW
Health, SA Dental, Dental Health Services WA and the WHO.

## Collection rules

* `robots.txt` is checked per host with `urllib.robotparser`; a 401/403 on
  `robots.txt` is treated as "disallow everything" (RFC 9309).
* At least 2.5 s between requests to the same host, plus any longer
  `Crawl-delay` the host declares; retries use exponential backoff.
* A descriptive user agent identifies the project.
* Raw HTML snapshots are stored with URL, final URL, HTTP status, SHA-256 and
  retrieval timestamp, so any answer can be traced to the exact page version.

## Sources that are in the manifest but disabled

`enabled: false` marks pages that `robots.txt` allows but whose **terms of use
prohibit automated collection**. The pipeline skips them, and they are excluded
from `corpus_version`.

| Source | Pages | Why disabled |
|---|---:|---|
| Australian Dental Association consumer site (`teeth.org.au`) | 10 | Terms of use (cl. 10.2, 41.7) forbid robots, spiders, screen scrapers or other automated copying without ADA's written consent. |
| Better Health Channel (Victorian Department of Health) | 13 | Terms of use prohibit screen scraping and republishing without written permission. |

To enable them, obtain written permission from the publisher, record it in
`docs/permissions/`, then set `enabled: true` and re-run `make ingest`. The
`corpus_version` hash will change, which is intended: results before and after
are not comparable.

## Sources that could not be collected

| Source | Status |
|---|---|
| Australian Institute of Health and Welfare (AIHW) | `robots.txt` and report pages return HTTP 403 behind a Cloudflare bot challenge. **This is why the corpus has little national statistical material**; the NSW public dental service data page partly fills the gap. Consider AIHW's data downloads or an API/permission request instead of crawling. |
| Queensland Health (`health.qld.gov.au`) | Same Cloudflare bot challenge (403). |
| Oral Health Victoria (formerly Dental Health Services Victoria) | Intermittent Cloudflare challenge on `robots.txt`; treated as disallow-all. |
| pregnancybirthbaby.org.au teething page | Rendered client-side; the HTML holds almost no text. |

## Licensing of what is indexed

| Organisation | Terms |
|---|---|
| healthdirect Australia | © Healthdirect Australia. Viewing and downloading permitted; modifying, republishing or creating derivative works needs permission. No anti-scraping clause found. |
| NSW Health | CC BY 4.0 — attribute "© State of New South Wales NSW Ministry of Health". |
| SA Dental | No published reuse licence; disclaimer and privacy pages only. |
| Dental Health Services WA | No published reuse licence; "Copyright © Dental Health Services, Government of Western Australia". |
| World Health Organization | Website content © WHO, all rights reserved; extracts may be used for research and private study, not commercially. Marked `secondary: true` and labelled non-Australian in answers. |

Implications for this project:

* Chunks are stored **locally** for retrieval and research; the repository
  redistributes none of them.
* Answers quote short passages with attribution and a link to the source page.
* Do not redistribute `data/index/chunks.jsonl` or a built Qdrant collection, and
  do not deploy this publicly as a commercial service without checking each
  publisher's terms.

## Provenance carried with every chunk

`chunk_id`, `source_id`, `source_org`, `url`, `page_title`, `section`,
`retrieved_at`, `jurisdiction`, `secondary`, `licence`, `tokens`,
`corpus_version` — see `api/app/rag/types.py`. The UI shows organisation,
section, jurisdiction and retrieval date on every citation chip.

## Re-running and versioning

```bash
make ingest           # uses cached snapshots where available
make ingest-refresh   # re-downloads every page
python -m ingest.cli stats
```

`corpus_version = sha256(enabled manifest entries, cleaned page contents,
chunking parameters, embedding model)`. It names the Qdrant collection, is stored
on every chunk, and is written into every turn log and evaluation report.
