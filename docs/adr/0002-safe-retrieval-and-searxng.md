# ADR 0002: Use bounded public-page retrieval and SearXNG search

- Status: Accepted
- Date: 26 July 2026

## Context

The first executable workflow used deterministic search results with inline
synthetic content. Real evidence retrieval introduces two separate trust
boundaries:

1. the configured search backend; and
2. arbitrary result URLs controlled by external pages and search engines.

Search snippets are insufficient as evidence. The system must fetch the source
page and extract visible text before an item can enter the evidence pipeline.
Fetching arbitrary URLs introduces SSRF, redirect, oversized-response, content
type, timeout, and prompt-injection risks.

## Decision

SearXNG is the first real search adapter. It is configured explicitly and uses
the documented JSON search endpoint. Mock search remains the default until a
trusted SearXNG URL is supplied.

Search candidates and fetched documents remain separate artifacts:

- SearXNG returns a URL, title, snippet, source category, and engine metadata.
- The snippet is never promoted directly to evidence.
- A safe fetcher validates and retrieves the result page.
- Visible text is extracted while script, style, template, SVG, and noscript
  content is discarded.
- Only the fetched text is handed to evidence classification.

The public-page fetcher:

- permits only HTTP and HTTPS;
- rejects URL credentials;
- restricts ports to 80 and 443;
- resolves and rejects non-public IP addresses;
- revalidates every redirect target;
- disables automatic redirects and environment proxy inheritance;
- limits redirects, time, response bytes, and content types;
- verifies HTTPS with the operating system certificate store;
- accepts textual HTML, XHTML, and plain-text content;
- accepts PDF bytes under a separate 20 MB response ceiling, validates their
  file signature, rejects encryption, and extracts text under 500-page and
  500,000-character limits;
- blocks PDF URLs before requesting them unless the source host is explicitly
  approved, and rejects an unexpected PDF response before reading its body.

An individual fetch failure is non-fatal. The source and extraction status are
persisted, a provider-failure trace event is emitted, and the next search
candidate is attempted within the configured page budget. If no usable
evidence remains, the workflow completes as unverifiable rather than failing.

The configured SearXNG base URL is a trusted service endpoint and may be local.
URLs returned by SearXNG do not inherit that trust.

Public availability does not establish permission to reproduce a document.
PDF hosts therefore require an explicit operator decision based on a license,
rights-holder permission, public-domain status, or an applicable legal
exception. The allowlist records that decision; it does not make the decision.

## Consequences

### Positive

- Search snippets cannot masquerade as exact evidence.
- Common SSRF targets and redirect-based bypasses are rejected before page
  retrieval.
- Search and fetching can be tested independently with injected transports.
- The existing search-provider contract remains stable for future adapters.

### Negative

- Image-only PDFs require a later, separately bounded OCR adapter.
- Dynamically rendered pages are not supported yet.
- Minimal HTML extraction does not identify the most relevant passage.
- DNS validation and the HTTP connection are separate operations; production
  deployments still require network-level egress restrictions or a
  DNS-pinning transport to fully address DNS rebinding.
- Claim analysis and judgment remain deterministic until a real model adapter
  is implemented.

## Follow-up

The next retrieval work is passage segmentation, claim-passage ranking,
canonical URL handling, deduplication, and extraction-status reporting. Browser
automation and OCR must be introduced only through separate bounded adapters.
