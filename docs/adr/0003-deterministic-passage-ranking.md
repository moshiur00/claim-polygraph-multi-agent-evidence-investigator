# ADR 0003: Rank bounded passages before evidence classification

- Status: Accepted
- Date: 26 July 2026

## Context

The first real-retrieval implementation safely extracted visible page text,
but handed as many as 12,000-14,000 characters to evidence classification as a
single passage. Whole-page evidence weakens citation precision, increases model
context, and can mix relevant statements with navigation, unrelated sections,
or qualifications.

## Decision

Every successfully extracted page is normalized into paragraph-aware text and
split into chunks of at most 1,200 characters. Each chunk records:

- source identifier;
- research path;
- ordinal position;
- exact start and end character offsets;
- normalized content hash.

Exact normalized duplicate chunks are removed within each research path.
Chunks are ranked against the normalized claim with a deterministic BM25-style
scorer. The highest-scoring passage from each required research path can enter
evidence classification. A zero-score passage remains stored for audit but
cannot become evidence.

Evidence records retain the selected chunk identifier, source-relative
character offsets, and retrieval score. This makes every evidence quotation
reproducible from the normalized source text.

## Consequences

### Positive

- Evidence is concise and tied to exact source positions.
- Support and contradiction research remain represented independently.
- Ranking is deterministic, inexpensive, local, and testable.
- A real model provider will receive substantially less irrelevant text.
- Zero-match navigation fragments cannot be promoted to evidence.

### Negative

- Lexical ranking can miss semantically relevant paraphrases.
- Character offsets refer to normalized extracted text, not raw HTML bytes.
- Selecting one passage per research path can omit useful secondary passages.
- Near-duplicate detection and cross-source evidence-family analysis are not
  included yet.

## Follow-up

Evaluate passage recall on a small annotated claim set. Add a local semantic
reranker only if it improves relevant-passage recall over this baseline. The
next model integration must consume selected chunks rather than complete pages.
