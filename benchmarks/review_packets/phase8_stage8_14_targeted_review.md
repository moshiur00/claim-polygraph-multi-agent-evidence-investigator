# Phase 8 Stage 8.14 targeted human-review packet

Status: **approved**

## Required disclosure

All candidate passages in this packet come from deterministic synthetic providers. They test role separation and containment, not real-world factual quality. They must not be described as externally verified evidence.

This review can approve the architecture and demonstrated role separation. It cannot claim that synthetic passages improve real-world factual accuracy.

## Decision requested

Does the multi-agent packet materially improve research structure enough to promote it as the default research subgraph while InvestigationService remains authoritative?

Promotion choices:

- `promote_observational_default`: run multi-agent research by default, but keep its evidence observational and keep InvestigationService authoritative.
- `hold`: retain the current observational opt-in/default arrangement pending a live reviewed evidence pilot.
- `reject`: remove the multi-agent subgraph from the promoted journey.

## CPNG-P01

**Claim:** A randomized trial found the treatment reduced symptoms by 20 percent.

**Authoritative verdict:** `mixed`

Authoritative evidence: 3; candidate additions: 3.

### Candidate 1 â€” primary_source

- Stance: `supports`
- Source: Mock official record (official)
- Publisher: Example Public Authority
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock official record supports: A randomized trial found the treatment reduced symptoms by 20 percent.

### Candidate 2 â€” challenger

- Stance: `qualifies`
- Source: Mock contrary record (primary_document)
- Publisher: Example Records Office
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock contrary record contradicts: A randomized trial found the treatment reduced symptoms by 20 percent.

### Candidate 3 â€” general_evidence

- Stance: `supports`
- Source: Mock contextual report (news)
- Publisher: Example Independent Newsroom
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock independent report qualifies: A randomized trial found the treatment reduced symptoms by 20 percent.

Review checklist:

- [x] Candidate roles are meaningfully distinct rather than duplicated.
- [x] The challenger contributes a real contradiction or qualification.
- [x] Evidence-family separation is structurally credible.
- [x] No candidate escaped into the authoritative packet.
- [x] The synthetic-fixture limitation is acceptable for architecture promotion only.

Case judgment: `improved`

Notes:

## CPNG-P02

**Claim:** The regulation entered into force in 2024 and applied immediately.

**Authoritative verdict:** `mixed`

Authoritative evidence: 3; candidate additions: 3.

### Candidate 1 â€” general_evidence

- Stance: `supports`
- Source: Mock contextual report (news)
- Publisher: Example Independent Newsroom
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock independent report qualifies: The regulation entered into force in 2024 and applied immediately.

### Candidate 2 â€” primary_source

- Stance: `supports`
- Source: Mock official record (official)
- Publisher: Example Public Authority
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock official record supports: The regulation entered into force in 2024 and applied immediately.

### Candidate 3 â€” challenger

- Stance: `qualifies`
- Source: Mock contrary record (primary_document)
- Publisher: Example Records Office
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock contrary record contradicts: The regulation entered into force in 2024 and applied immediately.

Review checklist:

- [x] Candidate roles are meaningfully distinct rather than duplicated.
- [x] The challenger contributes a real contradiction or qualification.
- [x] Evidence-family separation is structurally credible.
- [x] No candidate escaped into the authoritative packet.
- [x] The synthetic-fixture limitation is acceptable for architecture promotion only.

Case judgment: `improved`

Notes:

## CPNG-P03

**Claim:** The company was founded and commercially launched in the same year.

**Authoritative verdict:** `mixed`

Authoritative evidence: 3; candidate additions: 3.

### Candidate 1 â€” primary_source

- Stance: `supports`
- Source: Mock official record (official)
- Publisher: Example Public Authority
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock official record supports: The company was founded and commercially launched in the same year.

### Candidate 2 â€” challenger

- Stance: `qualifies`
- Source: Mock contrary record (primary_document)
- Publisher: Example Records Office
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock contrary record contradicts: The company was founded and commercially launched in the same year.

### Candidate 3 â€” general_evidence

- Stance: `supports`
- Source: Mock contextual report (news)
- Publisher: Example Independent Newsroom
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock independent report qualifies: The company was founded and commercially launched in the same year.

Review checklist:

- [x] Candidate roles are meaningfully distinct rather than duplicated.
- [x] The challenger contributes a real contradiction or qualification.
- [x] Evidence-family separation is structurally credible.
- [x] No candidate escaped into the authoritative packet.
- [x] The synthetic-fixture limitation is acceptable for architecture promotion only.

Case judgment: `improved`

Notes:

## CPNG-P04

**Claim:** The national population increased by 5 percent in 2023.

**Authoritative verdict:** `mixed`

Authoritative evidence: 3; candidate additions: 3.

### Candidate 1 â€” challenger

- Stance: `qualifies`
- Source: Mock contrary record (primary_document)
- Publisher: Example Records Office
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock contrary record contradicts: The national population increased by 5 percent in 2023.

### Candidate 2 â€” primary_source

- Stance: `supports`
- Source: Mock official record (official)
- Publisher: Example Public Authority
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock official record supports: The national population increased by 5 percent in 2023.

### Candidate 3 â€” general_evidence

- Stance: `supports`
- Source: Mock contextual report (news)
- Publisher: Example Independent Newsroom
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock independent report qualifies: The national population increased by 5 percent in 2023.

Review checklist:

- [x] Candidate roles are meaningfully distinct rather than duplicated.
- [x] The challenger contributes a real contradiction or qualification.
- [x] Evidence-family separation is structurally credible.
- [x] No candidate escaped into the authoritative packet.
- [x] The synthetic-fixture limitation is acceptable for architecture promotion only.

Case judgment: `improved`

Notes:

## CPNG-P05

**Claim:** The policy applies to every adult without exception.

**Authoritative verdict:** `mixed`

Authoritative evidence: 3; candidate additions: 3.

### Candidate 1 â€” general_evidence

- Stance: `supports`
- Source: Mock contextual report (news)
- Publisher: Example Independent Newsroom
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock independent report qualifies: The policy applies to every adult without exception.

### Candidate 2 â€” challenger

- Stance: `qualifies`
- Source: Mock contrary record (primary_document)
- Publisher: Example Records Office
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock contrary record contradicts: The policy applies to every adult without exception.

### Candidate 3 â€” primary_source

- Stance: `supports`
- Source: Mock official record (official)
- Publisher: Example Public Authority
- Rights: `unknown`; retention: `evidence_passages_only`
- Evidence family: `None`

> The mock official record supports: The policy applies to every adult without exception.

Review checklist:

- [x] Candidate roles are meaningfully distinct rather than duplicated.
- [x] The challenger contributes a real contradiction or qualification.
- [x] Evidence-family separation is structurally credible.
- [x] No candidate escaped into the authoritative packet.
- [x] The synthetic-fixture limitation is acceptable for architecture promotion only.

Case judgment: `improved`

Notes:

## Human decision record

- Reviewer identity: Md Moshiur Rahman
- Review date: 28 July 2026
- Decision: `promote_observational_default`
- Rationale: All five cases were judged improved. Promote the multi-agent research subgraph as the observational default while preserving InvestigationService authority and the synthetic-fixture limitation.
- Distinct approver identity: Md Rashedul Islam
- Approval date: 28 July 2026
- Approval decision: `approve`

The targeted human-review and distinct-approval gates are complete. ADR 0020 records the accepted observational-default promotion.

