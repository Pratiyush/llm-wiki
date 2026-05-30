# Web URL Import Design

## Problem

Knowledge can currently enter a notebook only through uploaded files. Users need to add public web pages, including government legal/regulatory pages and public article pages, as notebook knowledge sources. Answers that use those imported web pages must cite the source URL clearly, not only the generated wiki page title.

Many target pages may reject server-side fetches, require login, show anti-bot challenges, or render meaningful content only in the browser. The first version should not try to bypass those controls. It should provide a reliable fallback that still preserves the URL as citation metadata.

## Goals

- Add a web import path alongside file upload.
- Support public `http` and `https` URLs in the selected notebook.
- Fetch and extract readable title/body text when the page is publicly accessible.
- Provide a manual fallback: URL + title/body paste, so users can import content when automatic fetch fails.
- Persist URL metadata in generated source pages.
- Ensure Q&A prompts expose web source URLs so generated answers can cite them explicitly.
- Reuse notebook permissions, lineage, cache invalidation, and knowledge extraction conventions where practical.
- Return clear user-facing failure reasons for inaccessible or unparseable pages.

## Non-Goals

- No login session or cookie management.
- No captcha solving or anti-bot bypass.
- No headless browser rendering in the first version.
- No recursive website crawling.
- No scheduled refresh or diffing of web pages.
- No attempt to determine legal availability beyond public HTTP access and user-provided pasted text.

## User Experience

The upload tab gains a second import area for web pages.

Primary path:

1. User selects a notebook.
2. User enters a public URL and optional version/source note.
3. User clicks import.
4. Server fetches the URL, extracts title and body, creates a web source page, and records lineage.
5. UI shows success with the wiki path and canonical URL.

Fallback path:

1. Automatic fetch fails, or user chooses manual paste directly.
2. User enters URL, title, body text, and optional note.
3. Server validates URL and body length, then creates a web source page using the pasted body.
4. The generated page still stores `source_url`, so later answers can cite the URL.

Failures are specific:

- Unsupported URL scheme.
- Private, loopback, or cloud metadata address blocked.
- HTTP 403/429 or other fetch rejection.
- Timeout.
- Empty or unreadable body.
- Body too short or too large.

## Backend API

Add `POST /api/upload/url`.

Request body:

```json
{
  "url": "https://example.gov.cn/rule.html",
  "title": "Optional manual title",
  "content": "Optional pasted body text",
  "version_note": "Optional source note",
  "notebook": "enterprise-management",
  "mode": "auto"
}
```

Modes:

- `auto`: server fetches the URL and extracts content.
- `manual`: server uses pasted `title` and `content`, still validates and stores `url`.

Authentication:

- Accept the same bearer token pattern as file upload.
- Enforce notebook access with the same `can_access_notebook` checks.

Response on success:

```json
{
  "status": "ok",
  "source_type": "web",
  "url": "https://example.gov.cn/rule.html",
  "canonical_url": "https://example.gov.cn/rule.html",
  "title": "Rule title",
  "wiki_path": "sources/web/rule-title.md",
  "content_length": 12345,
  "entities_extracted": 3,
  "concepts_extracted": 2,
  "new_pages": []
}
```

Response on handled failure:

```json
{
  "status": "error",
  "code": "fetch_forbidden",
  "message": "The target site rejected server-side fetching (HTTP 403). Use URL + pasted body import to preserve this URL as the citation source."
}
```

## Fetching And Extraction

Create a small service such as `llmwiki/web/services/web_ingester.py`.

Automatic fetch:

- Allow only `http` and `https`.
- Resolve host before connecting and block unsafe targets:
  - localhost and loopback.
  - private RFC1918 ranges.
  - link-local ranges.
  - cloud metadata IPs such as `169.254.169.254`.
  - invalid hostnames and raw file paths.
- Use a bounded timeout.
- Follow ordinary redirects, but revalidate the final URL after redirect.
- Limit downloaded bytes.
- Send a normal descriptive `User-Agent`, without pretending to be a logged-in browser.
- Decode by charset header when present, otherwise use safe UTF-8 fallback.

Extraction:

- Title from `<title>`, `og:title`, or first heading.
- Canonical URL from `<link rel="canonical">` when safe; otherwise final URL.
- Remove scripts, styles, navigation-like markup, and hidden noise where practical.
- Prefer article/main/body text in that order.
- Normalize whitespace and keep paragraph breaks.
- Reject near-empty extracted content with a clear error.

Manual paste:

- Validate URL with the same URL safety rules, but do not fetch.
- Require body text above a minimum length.
- Use supplied title or derive a title from URL.
- Mark the source page as manually captured.

## Source Page Format

Web source pages live under:

```text
wiki/sources/web/<slug>.md
```

Notebook-scoped paths use the notebook wiki root, matching file upload behavior.

Frontmatter:

```markdown
---
title: "Page title"
type: source
tags: [web-source]
date: 2026-05-30
source_type: web
source_url: "https://example.gov.cn/rule.html"
canonical_url: "https://example.gov.cn/rule.html"
fetched_at: "2026-05-30T12:00:00+08:00"
capture_method: auto
project: web
---
```

Body starts with a visible source section:

```markdown
## Source

- URL: https://example.gov.cn/rule.html
- Canonical URL: https://example.gov.cn/rule.html
- Captured at: 2026-05-30T12:00:00+08:00
- Capture method: auto
```

Then the usual `Summary`, `Key Claims`, `Connections`, and full extracted body.

## Q&A Citation Behavior

The existing wiki context builder currently labels pages mainly by path and title. Update it so when `read_page()` metadata contains `source_type: web` and `source_url`, prompt context includes:

```text
Web source URL: https://example.gov.cn/rule.html
```

Update answer instructions for both normal and agent modes:

- Internal documents continue to cite with `[[Page Title]]`.
- Web sources must cite with both `[[Page Title]]` and the exact URL shown in the source metadata.
- If a quote or claim comes from a pasted manual web capture, cite the same stored `source_url`.

This does not guarantee model obedience by itself, but it gives the model the URL in context and adds an explicit formatting requirement. Tests should verify the prompt/context assembly includes the URL for web pages.

## Data Model And Lineage

Use the existing `UploadedFile` and `KnowledgeLineage` tables for first version compatibility:

- `UploadedFile.filename`: web page title or URL-derived name.
- `UploadedFile.wiki_path`: generated web source page.
- `UploadedFile.version_note`: source note.
- `KnowledgeLineage.wiki_type`: `source`, `entity`, `concept` as today.

Avoid a database migration in the first pass. The authoritative web metadata lives in the source page frontmatter. A later migration can add `source_kind` and `source_url` columns if management screens need native filtering.

## Tests

Focused unit tests:

- URL validation blocks unsupported schemes and unsafe hosts.
- Auto import creates a web source page with `source_url`, `canonical_url`, `fetched_at`, and `capture_method`.
- Manual import creates a web source page without fetching and preserves URL.
- Fetch failure returns a specific error and fallback message.
- Wiki context builder includes web source URL in prompt context.
- Upload route enforces notebook access for URL import.

Use mocked fetch responses; do not depend on external network availability.

## Risks And Mitigations

- Anti-bot pages: return specific failure and offer manual paste fallback.
- SSRF: strict URL/host/IP validation before fetch and after redirects.
- Poor extraction quality: keep full extracted text visible in source pages and allow manual paste when auto extraction is weak.
- Citation omission by model: include URL in prompt context and explicit citation rules; add tests for context assembly, not model output.
- Duplicate imports: first version may allow duplicates; deduplication by canonical URL can be added later.

## Acceptance Criteria

- A user can import a public government/regulation web page into a notebook from the upload tab.
- A user can import a blocked page by pasting URL + text.
- Generated source pages contain visible and frontmatter URL metadata.
- Q&A context includes web source URLs for imported web pages.
- The UI clearly reports anti-bot/fetch failures and points to manual paste fallback.
- Existing file upload behavior remains unchanged.
