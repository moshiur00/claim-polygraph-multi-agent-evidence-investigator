"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

type Span = { start_char: number; end_char: number; quoted_text: string };
type EvidenceSpan = Span & { evidence_id: string };
type Evidence = {
  evidence_id: string;
  title: string;
  url: string;
  source_class: string;
  passage: string;
};
type Annotation = {
  annotator_identity: string;
  annotated_on: string;
  dimension_bucket: string;
  comparator_or_relation: string;
  gold_label: string;
  claim_span: Span | null;
  evidence_spans: EvidenceSpan[];
  expected_verification_state: string | null;
  ambiguity_notes: string[];
};
type Approval = {
  approver_identity: string;
  approved_on: string;
  decision: "approve" | "return_for_revision";
  checked_dimension: boolean;
  checked_relation: boolean;
  checked_claim_span: boolean;
  checked_evidence_spans: boolean;
  checked_gold_label: boolean;
  checked_expected_state: boolean;
  notes: string[];
};
type Case = {
  case_id: string;
  source_candidate_id: string;
  split: string;
  origin_family_id: string;
  claim_text: string;
  evidence: Evidence[];
  proposal: {
    dimension_bucket: string | null;
    comparator_or_relation: string | null;
    claim_span: Span;
    evidence_spans: EvidenceSpan[];
    suggested_gold_label?: string | null;
    suggested_verification_state?: string | null;
    machine_notes?: string[];
  };
  annotation: Annotation | null;
  approval: Approval | null;
};
type Workbook = {
  workbook_id: string;
  schema_version: number;
  frozen: boolean;
  cases: Case[];
  _simulation_notice?: unknown;
};

const dimensions = [
  "percentage_or_rate", "count", "pressure", "currency", "speed",
  "temperature", "duration", "distance_or_mass", "temporal_instant",
  "temporal_interval_or_status",
];
const labels = [
  "deterministic_constructible", "fallback_eligible",
  "unconstructible", "not_applicable",
];
const states = ["verified", "contradicted", "qualified", "insufficient", "error"];
const labelTargets: Record<string, number> = {
  deterministic_constructible: 30,
  fallback_eligible: 15,
  unconstructible: 10,
  not_applicable: 5,
};
const dimensionTargets = Object.fromEntries(dimensions.map((item) => [item, 6]));
const today = new Date().toISOString().slice(0, 10);
const storageKey = "claim-polygraph-v3-annotation-workbook-v1";
const title = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());

function emptyAnnotation(record: Case): Annotation {
  const label = record.proposal.suggested_gold_label ?? "";
  const constructible = ["deterministic_constructible", "fallback_eligible"].includes(label);
  return {
    annotator_identity: "Md Moshiur Rahman",
    annotated_on: today,
    dimension_bucket: record.proposal.dimension_bucket ?? "",
    comparator_or_relation: record.proposal.comparator_or_relation ?? "",
    gold_label: label,
    claim_span: constructible ? { ...record.proposal.claim_span } : null,
    evidence_spans: constructible
      ? record.proposal.evidence_spans.map((span) => ({ ...span }))
      : [],
    expected_verification_state: constructible
      ? record.proposal.suggested_verification_state ?? null
      : null,
    ambiguity_notes: record.proposal.machine_notes?.slice(2) ?? [],
  };
}

function emptyApproval(): Approval {
  return {
    approver_identity: "Md Rashedul Islam",
    approved_on: today,
    decision: "return_for_revision",
    checked_dimension: false,
    checked_relation: false,
    checked_claim_span: false,
    checked_evidence_spans: false,
    checked_gold_label: false,
    checked_expected_state: false,
    notes: [],
  };
}

function annotationProblems(record: Case) {
  const problems: string[] = [];
  const annotation = record.annotation;
  if (!annotation) return ["Annotation missing"];
  if (!annotation.annotator_identity.trim()) problems.push("Annotator identity missing");
  if (annotation.annotator_identity.toLowerCase().startsWith("ai-assisted draft")) {
    problems.push("AI draft has not been accepted by a human annotator");
  }
  if (!dimensions.includes(annotation.dimension_bucket)) problems.push("Dimension missing");
  if (!annotation.comparator_or_relation.trim()) problems.push("Relation missing");
  if (!labels.includes(annotation.gold_label)) problems.push("Construction label missing");
  const constructible = ["deterministic_constructible", "fallback_eligible"].includes(annotation.gold_label);
  if (constructible && !annotation.expected_verification_state) problems.push("Expected state missing");
  if (constructible && (!annotation.claim_span || annotation.evidence_spans.length === 0)) problems.push("Exact spans missing");
  if (!constructible && (annotation.claim_span || annotation.evidence_spans.length || annotation.expected_verification_state)) {
    problems.push("Non-constructible case must omit gold spans and state");
  }
  if (annotation.claim_span) {
    const span = annotation.claim_span;
    if (record.claim_text.slice(span.start_char, span.end_char) !== span.quoted_text) problems.push("Claim offsets invalid");
  }
  for (const span of annotation.evidence_spans) {
    const evidence = record.evidence.find((item) => item.evidence_id === span.evidence_id);
    if (!evidence || evidence.passage.slice(span.start_char, span.end_char) !== span.quoted_text) {
      problems.push(`Evidence offsets invalid: ${span.evidence_id}`);
    }
  }
  return problems;
}

function caseProblems(record: Case) {
  const problems = annotationProblems(record);
  const annotation = record.annotation;
  const approval = record.approval;
  if (!annotation) return problems;
  if (!approval) return [...problems, "Approval missing"];
  if (!approval.approver_identity.trim()) problems.push("Approver identity missing");
  if (approval.approver_identity.trim().toLowerCase() === annotation.annotator_identity.trim().toLowerCase()) {
    problems.push("Approver must be distinct");
  }
  const checks = Object.entries(approval).filter(([key]) => key.startsWith("checked_"));
  if (approval.decision !== "approve") problems.push("Not approved");
  if (checks.some(([, value]) => !value)) problems.push("Approval checklist incomplete");
  return problems;
}

export default function AnnotationStudio() {
  const [workbook, setWorkbook] = useState<Workbook | null>(null);
  const [selected, setSelected] = useState(0);
  const [filter, setFilter] = useState<"all" | "problems" | "pending">("all");
  const [splitFilter, setSplitFilter] = useState<"all" | "development" | "calibration" | "held_out">("all");
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!workbook) return;
    localStorage.setItem(storageKey, JSON.stringify(workbook));
  }, [workbook]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (!workbook || !event.altKey) return;
      if (event.key === "ArrowRight") {
        event.preventDefault();
        setSelected((value) => Math.min(workbook.cases.length - 1, value + 1));
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        setSelected((value) => Math.max(0, value - 1));
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [workbook]);

  const cases = useMemo(() => workbook?.cases ?? [], [workbook]);
  const isReplacementCalibration = Boolean(
    workbook?.workbook_id.startsWith("verification-construction-v3-stage6")
    || workbook?.workbook_id === "verification-construction-v4-stage8-fresh-calibration-workbook-v1"
    || workbook?.workbook_id === "verification-construction-v4-stage9b-fresh-calibration-workbook-v1"
    || workbook?.workbook_id === "verification-construction-v4-stage9e-fresh-calibration-workbook-v1"
    || workbook?.workbook_id === "verification-construction-v4-stage10-fresh-held-out-workbook-v1"
  );
  const isStage6cCalibration = workbook?.workbook_id ===
    "verification-construction-v3-stage6c-fresh-calibration-workbook-v1";
  const isStage6eCalibration = workbook?.workbook_id ===
    "verification-construction-v3-stage6e-fresh-calibration-workbook-v1";
  const isV4Calibration = workbook?.workbook_id ===
    "verification-construction-v4-stage8-fresh-calibration-workbook-v1";
  const isV49bCalibration = workbook?.workbook_id ===
    "verification-construction-v4-stage9b-fresh-calibration-workbook-v1";
  const isV49eCalibration = workbook?.workbook_id ===
    "verification-construction-v4-stage9e-fresh-calibration-workbook-v1";
  const isV410HeldOut = workbook?.workbook_id ===
    "verification-construction-v4-stage10-fresh-held-out-workbook-v1";
  const current = cases[selected] ?? null;
  const counts = useMemo(() => {
    const labelCounts: Record<string, number> = {};
    const dimensionCounts: Record<string, number> = {};
    let annotated = 0;
    let approved = 0;
    let valid = 0;
    for (const record of cases) {
      if (record.annotation) {
        annotated += 1;
        labelCounts[record.annotation.gold_label] = (labelCounts[record.annotation.gold_label] ?? 0) + 1;
        dimensionCounts[record.annotation.dimension_bucket] = (dimensionCounts[record.annotation.dimension_bucket] ?? 0) + 1;
      }
      if (record.approval?.decision === "approve") approved += 1;
      if (caseProblems(record).length === 0) valid += 1;
    }
    return { labelCounts, dimensionCounts, annotated, approved, valid };
  }, [cases]);

  const visible = useMemo(() => cases.map((record, index) => ({ record, index })).filter(({ record }) => {
    const searchHit = !query || `${record.case_id} ${record.claim_text}`.toLowerCase().includes(query.toLowerCase());
    if (!searchHit) return false;
    if (splitFilter !== "all" && record.split !== splitFilter) return false;
    if (filter === "problems") return caseProblems(record).length > 0;
    if (filter === "pending") return !record.annotation || record.approval?.decision !== "approve";
    return true;
  }), [cases, filter, query, splitFilter]);

  function resumeSavedWorkbook() {
    try {
      const saved = localStorage.getItem(storageKey);
      if (!saved) {
        setMessage("No browser-saved review was found on this device.");
        return;
      }
      const parsed = JSON.parse(saved) as Workbook;
      if (!Array.isArray(parsed.cases) || ![20, 60].includes(parsed.cases.length)) throw new Error("Saved review is not a recognized 20- or 60-case workbook.");
      setWorkbook(parsed);
      setSelected(0);
      setMessage("Browser-saved review restored.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Saved review could not be restored.");
    }
  }

  async function loadAiDraft() {
    try {
      const response = await fetch("/v3-ai-annotation-draft.json");
      if (!response.ok) throw new Error("The packaged AI draft is unavailable.");
      const parsed = await response.json() as Workbook;
      if (!Array.isArray(parsed.cases) || parsed.cases.length !== 60) throw new Error("The AI draft is not a valid 60-case workbook.");
      setWorkbook(parsed);
      setSelected(0);
      setMessage("AI suggestions loaded. They are not human annotations; review each case and replace the draft identity.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The AI draft could not be loaded.");
    }
  }

  async function loadReplacementCalibration() {
    try {
      const response = await fetch("/v3-stage6a-replacement-calibration.json");
      if (!response.ok) throw new Error("The V3.6a replacement workbook is unavailable.");
      const parsed = await response.json() as Workbook;
      if (!Array.isArray(parsed.cases) || parsed.cases.length !== 20) throw new Error("The replacement workbook is not a valid 20-case packet.");
      setWorkbook(parsed);
      setSelected(0);
      setMessage("Fresh V3.6a calibration cases loaded. Human annotation and distinct approval are required before calibration can run.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The replacement workbook could not be loaded.");
    }
  }

  async function loadStage6cCalibration() {
    try {
      const response = await fetch("/v3-stage6c-fresh-calibration.json");
      if (!response.ok) throw new Error("The V3.6c fresh workbook is unavailable.");
      const parsed = await response.json() as Workbook;
      if (!Array.isArray(parsed.cases) || parsed.cases.length !== 20) throw new Error("The V3.6c workbook is not a valid 20-case packet.");
      setWorkbook(parsed);
      setSelected(0);
      setMessage("Fresh V3.6c calibration cases loaded. Human annotation and distinct approval are required before the one-time calibration.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The V3.6c workbook could not be loaded.");
    }
  }

  async function loadStage6eCalibration() {
    try {
      const response = await fetch("/v3-stage6e-fresh-calibration.json");
      if (!response.ok) throw new Error("The V3.6e fresh workbook is unavailable.");
      const parsed = await response.json() as Workbook;
      if (!Array.isArray(parsed.cases) || parsed.cases.length !== 20) throw new Error("The V3.6e workbook is not a valid 20-case packet.");
      setWorkbook(parsed);
      setSelected(0);
      setMessage("Fresh V3.6e suggestions loaded with reviewer names prefilled. Review each case, record the annotation, then obtain distinct approval.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The V3.6e workbook could not be loaded.");
    }
  }

  async function loadV4Calibration() {
    try {
      const response = await fetch("/v4-stage8-fresh-calibration.json");
      if (!response.ok) throw new Error("The V4.8 fresh workbook is unavailable.");
      const parsed = await response.json() as Workbook;
      if (!Array.isArray(parsed.cases) || parsed.cases.length !== 20) throw new Error("The V4.8 workbook is not a valid 20-case packet.");
      setWorkbook(parsed);
      setSelected(0);
      setMessage("Fresh V4.8 proposals loaded with reviewer names prefilled. Review every annotation, then obtain distinct approval before calibration.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The V4.8 workbook could not be loaded.");
    }
  }

  async function loadV49bCalibration() {
    try {
      const response = await fetch("/v4-stage9b-fresh-calibration.json");
      if (!response.ok) throw new Error("The V4.9b fresh workbook is unavailable.");
      const parsed = await response.json() as Workbook;
      if (!Array.isArray(parsed.cases) || parsed.cases.length !== 20) throw new Error("The V4.9b workbook is not a valid 20-case packet.");
      setWorkbook(parsed);
      setSelected(0);
      setMessage("Fresh V4.9b proposals loaded with both reviewer names prefilled. Review every annotation, then obtain distinct approval before calibration.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The V4.9b workbook could not be loaded.");
    }
  }

  async function loadV49eCalibration() {
    try {
      const response = await fetch("/v4-stage9e-fresh-calibration.json");
      if (!response.ok) throw new Error("The V4.9e fresh workbook is unavailable.");
      const parsed = await response.json() as Workbook;
      if (!Array.isArray(parsed.cases) || parsed.cases.length !== 20) throw new Error("The V4.9e workbook is not a valid 20-case packet.");
      setWorkbook(parsed);
      setSelected(0);
      setMessage("Fresh V4.9e proposals loaded with both reviewer names prefilled. Review every annotation, then obtain distinct approval before calibration.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The V4.9e workbook could not be loaded.");
    }
  }

  async function loadV410HeldOut() {
    try {
      const response = await fetch("/v4-stage10-fresh-held-out.json");
      if (!response.ok) throw new Error("The V4.10 sealed held-out workbook is unavailable.");
      const parsed = await response.json() as Workbook;
      if (!Array.isArray(parsed.cases) || parsed.cases.length !== 20) throw new Error("The V4.10 workbook is not a valid 20-case packet.");
      setWorkbook(parsed);
      setSelected(0);
      setMessage("Sealed V4.10 held-out proposals loaded with both reviewer names prefilled. Review every annotation and obtain distinct approval; this does not authorize model execution.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The V4.10 held-out workbook could not be loaded.");
    }
  }

  function importWorkbook(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result)) as Workbook;
        if (!Array.isArray(parsed.cases) || ![20, 60].includes(parsed.cases.length)) throw new Error("Expected a recognized 20- or 60-case workbook.");
        setWorkbook(parsed);
        setSelected(0);
        setMessage(parsed._simulation_notice
          ? "Imported. Simulation metadata will be removed on export; every human decision must still be reviewed."
          : "Workbook imported successfully.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "The workbook could not be read.");
      }
    };
    reader.readAsText(file);
  }

  function updateCase(update: (record: Case) => Case) {
    if (!workbook || !current) return;
    const next = [...workbook.cases];
    next[selected] = update(current);
    setWorkbook({ ...workbook, cases: next });
  }

  function setAnnotation(patch: Partial<Annotation>) {
    updateCase((record) => {
      const annotation = { ...(record.annotation ?? emptyAnnotation(record)), ...patch };
      const constructible = ["deterministic_constructible", "fallback_eligible"].includes(annotation.gold_label);
      if (!constructible && annotation.gold_label) {
        annotation.claim_span = null;
        annotation.evidence_spans = [];
        annotation.expected_verification_state = null;
      }
      return { ...record, annotation };
    });
  }

  function setApproval(patch: Partial<Approval>) {
    updateCase((record) => ({ ...record, approval: { ...(record.approval ?? emptyApproval()), ...patch } }));
  }

  function recordReviewedAnnotation() {
    if (!current) return;
    const annotation = current.annotation ?? emptyAnnotation(current);
    updateCase((record) => ({ ...record, annotation }));
    setMessage(`${current.case_id} recorded as reviewed by ${annotation.annotator_identity}.`);
  }

  function updateClaimSpan(key: "start_char" | "end_char", value: number) {
    if (!current?.annotation?.claim_span) return;
    const span = { ...current.annotation.claim_span, [key]: value };
    span.quoted_text = current.claim_text.slice(span.start_char, span.end_char);
    setAnnotation({ claim_span: span });
  }

  function toggleEvidence(evidence: Evidence, enabled: boolean) {
    if (!current?.annotation) return;
    const spans = current.annotation.evidence_spans.filter((span) => span.evidence_id !== evidence.evidence_id);
    if (enabled) spans.push({ evidence_id: evidence.evidence_id, start_char: 0, end_char: evidence.passage.length, quoted_text: evidence.passage });
    setAnnotation({ evidence_spans: spans });
  }

  function updateEvidenceSpan(evidence: Evidence, key: "start_char" | "end_char", value: number) {
    if (!current?.annotation) return;
    const spans = current.annotation.evidence_spans.map((span) => {
      if (span.evidence_id !== evidence.evidence_id) return span;
      const next = { ...span, [key]: value };
      next.quoted_text = evidence.passage.slice(next.start_char, next.end_char);
      return next;
    });
    setAnnotation({ evidence_spans: spans });
  }

  function approveCurrent() {
    if (!current?.annotation) return;
    const approval = current.approval ?? emptyApproval();
    const identityDistinct = approval.approver_identity.trim()
      && approval.approver_identity.trim().toLowerCase() !== current.annotation.annotator_identity.trim().toLowerCase();
    if (!identityDistinct) {
      setMessage("Enter an approver identity that is different from the annotator.");
      return;
    }
    if (!window.confirm("Confirm that the named approver personally checked all six items for this case.")) return;
    setApproval({
      decision: "approve",
      checked_dimension: true,
      checked_relation: true,
      checked_claim_span: true,
      checked_evidence_spans: true,
      checked_gold_label: true,
      checked_expected_state: true,
    });
    setMessage(`${current.case_id} recorded as independently approved.`);
  }

  function copyIdentitiesToSplit() {
    if (!workbook || !current || splitFilter === "all") {
      setMessage("Choose Development, Calibration or Held Out before copying identities.");
      return;
    }
    const annotator = (current.annotation ?? emptyAnnotation(current)).annotator_identity.trim();
    const approver = (current.approval ?? emptyApproval()).approver_identity.trim();
    if (!annotator && !approver) {
      setMessage("Enter an annotator or approver identity on the current case first.");
      return;
    }
    if (annotator && approver && annotator.toLowerCase() === approver.toLowerCase()) {
      setMessage("Annotator and approver identities must be different.");
      return;
    }
    const next = workbook.cases.map((record) => {
      if (record.split !== splitFilter) return record;
      const annotation = { ...(record.annotation ?? emptyAnnotation(record)) };
      const approval = { ...(record.approval ?? emptyApproval()) };
      if (annotator && !annotation.annotator_identity.toLowerCase().startsWith("ai-assisted draft")) {
        annotation.annotator_identity = annotator;
      }
      if (approver) approval.approver_identity = approver;
      return { ...record, annotation, approval };
    });
    setWorkbook({ ...workbook, cases: next });
    setMessage(`Reviewer identities copied to eligible ${title(splitFilter)} cases. AI draft identities remain until each case is reviewed.`);
  }

  function approveReviewedSplit() {
    if (!workbook || splitFilter === "all") {
      setMessage("Choose one split before recording batch approval.");
      return;
    }
    const splitCases = workbook.cases.filter((record) => record.split === splitFilter);
    const eligible = splitCases.filter((record) => {
      if (annotationProblems(record).length || !record.annotation || !record.approval?.approver_identity.trim()) return false;
      return record.annotation.annotator_identity.trim().toLowerCase() !== record.approval.approver_identity.trim().toLowerCase();
    });
    if (eligible.length !== splitCases.length) {
      setMessage(`${splitCases.length - eligible.length} ${title(splitFilter)} case(s) still lack a complete annotation or distinct approver identity.`);
      return;
    }
    if (!window.confirm(`Confirm that each named approver personally checked all six checkpoints for all ${splitCases.length} ${title(splitFilter)} cases.`)) return;
    const eligibleIds = new Set(eligible.map((record) => record.case_id));
    const next = workbook.cases.map((record) => eligibleIds.has(record.case_id)
      ? {
          ...record,
          approval: {
            ...(record.approval as Approval),
            decision: "approve" as const,
            checked_dimension: true,
            checked_relation: true,
            checked_claim_span: true,
            checked_evidence_spans: true,
            checked_gold_label: true,
            checked_expected_state: true,
          },
        }
      : record);
    setWorkbook({ ...workbook, cases: next });
    setMessage(`${title(splitFilter)} split recorded as independently approved.`);
  }

  function exportWorkbook() {
    if (!workbook) return;
    const invalid = workbook.cases.filter((record) => caseProblems(record).length > 0);
    const labelOk = isReplacementCalibration || Object.entries(labelTargets).every(([key, target]) => (counts.labelCounts[key] ?? 0) === target);
    const dimensionsOk = isReplacementCalibration || Object.entries(dimensionTargets).every(([key, target]) => (counts.dimensionCounts[key] ?? 0) === target);
    if (invalid.length) {
      setMessage(`Export blocked: ${invalid.length} case(s) still have annotation or approval problems.`);
      return;
    }
    const { _simulation_notice: _removed, ...clean } = workbook;
    void _removed;
    const blob = new Blob([`${JSON.stringify(clean, null, 2)}\n`], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const quotaDeviation = !labelOk || !dimensionsOk;
    link.download = isV410HeldOut
      ? "verification_construction_v4_stage10_fresh_held_out_workbook_v1_APPROVED.json"
      : isV49eCalibration
      ? "verification_construction_v4_stage9e_fresh_calibration_workbook_v1_APPROVED.json"
      : isV49bCalibration
      ? "verification_construction_v4_stage9b_fresh_calibration_workbook_v1_APPROVED.json"
      : isV4Calibration
      ? "verification_construction_v4_stage8_fresh_calibration_workbook_v1_APPROVED.json"
      : isStage6eCalibration
      ? "verification_construction_v3_stage6e_fresh_calibration_workbook_v1_APPROVED.json"
      : isStage6cCalibration
      ? "verification_construction_v3_stage6c_fresh_calibration_workbook_v1_APPROVED.json"
      : isReplacementCalibration
      ? "verification_construction_v3_stage6a_replacement_calibration_workbook_v1_APPROVED.json"
      : quotaDeviation
        ? "verification_construction_v3_annotation_workbook_v1_APPROVED_WITH_QUOTA_DEVIATION.json"
        : "verification_construction_v3_annotation_workbook_v1_APPROVED.json";
    link.click();
    URL.revokeObjectURL(url);
    setMessage(quotaDeviation
      ? "Approved workbook exported. Frozen quota deviations remain and must be resolved or formally amended before benchmark freeze."
      : "Clean approved workbook exported; all case and quota gates pass.");
  }

  if (!workbook) {
    return <main className="annotation-empty">
      <section>
        <span>CLAIM POLYGRAPH · V3.2</span>
        <h1>Human Annotation Studio</h1>
        <p>Review numerical and temporal construction cases with exact evidence spans, independent approval and live quota safeguards.</p>
        <button onClick={() => fileRef.current?.click()}>Import annotation workbook</button>
        <button className="annotation-resume" onClick={loadV410HeldOut}>Start V4.10 sealed held-out review</button>
        <button className="annotation-resume" onClick={loadV49eCalibration}>Start V4.9e fresh calibration review</button>
        <button className="annotation-resume" onClick={loadV49bCalibration}>Start V4.9b fresh calibration review</button>
        <button className="annotation-resume" onClick={loadV4Calibration}>Start V4.8 fresh calibration review</button>
        <button className="annotation-resume" onClick={loadStage6eCalibration}>Start V3.6e fresh review</button>
        <button className="annotation-resume" onClick={loadStage6cCalibration}>Start V3.6c fresh review</button>
        <button className="annotation-resume" onClick={loadReplacementCalibration}>Start V3.6a replacement review</button>
        <button className="annotation-resume" onClick={loadAiDraft}>Start from AI-filled draft</button>
        <button className="annotation-resume" onClick={resumeSavedWorkbook}>Resume browser-saved review</button>
        <input ref={fileRef} hidden type="file" accept=".json,application/json" onChange={importWorkbook} />
        <Link href="/">Return to investigation dashboard</Link>
      </section>
    </main>;
  }

  const problems = current ? caseProblems(current) : [];
  const annotation = current?.annotation ?? (current ? emptyAnnotation(current) : null);
  const approval = current?.approval ?? emptyApproval();

  return <main className="annotation-shell">
    <header className="annotation-header">
      <div><span>CLAIM POLYGRAPH · V3.2</span><h1>Human Annotation Studio</h1></div>
      <div className="annotation-header-actions">
        <small>{counts.valid} of {cases.length} cases release-ready · saved automatically</small>
        <button onClick={() => fileRef.current?.click()}>Import</button>
        <button className="annotation-export" onClick={exportWorkbook}>Export approved workbook</button>
        <input ref={fileRef} hidden type="file" accept=".json,application/json" onChange={importWorkbook} />
      </div>
    </header>

    <section className="annotation-progress" aria-label="Review progress">
      <div><b>{counts.annotated}</b><span>Annotated</span></div>
      <div><b>{counts.approved}</b><span>Approved</span></div>
      <div><b>{cases.length - counts.valid}</b><span>Need attention</span></div>
      <div className="annotation-progress-bar"><i style={{ width: `${Math.round(counts.valid / cases.length * 100)}%` }} /></div>
    </section>

    {message && <div className="annotation-message" role="status">{message}<button aria-label="Dismiss notification" onClick={() => setMessage("")}>×</button></div>}

    <div className="annotation-layout">
      <aside className="annotation-case-list">
        <div className="annotation-list-tools">
          <input aria-label="Search cases" placeholder="Search case or claim…" value={query} onChange={(e) => setQuery(e.target.value)} />
          <div>{(["all", "problems", "pending"] as const).map((item) =>
            <button key={item} className={filter === item ? "active" : ""} onClick={() => setFilter(item)}>{title(item)}</button>)}</div>
          <select aria-label="Filter by split" value={splitFilter} onChange={(e) => setSplitFilter(e.target.value as typeof splitFilter)}>
            <option value="all">All splits</option>
            <option value="development">Development · 20</option>
            <option value="calibration">Calibration · 20</option>
            <option value="held_out">Held out · 20</option>
          </select>
          <small>Alt + ← / → moves between cases</small>
        </div>
        <div className="annotation-cases">
          {visible.map(({ record, index }) => {
            const issueCount = caseProblems(record).length;
            return <button key={record.case_id} className={selected === index ? "selected" : ""} onClick={() => setSelected(index)}>
              <span>{record.case_id}<em>{record.split}</em></span>
              <strong>{record.claim_text}</strong>
              <small className={issueCount ? "problem" : "ready"}>{issueCount ? `${issueCount} issue${issueCount === 1 ? "" : "s"}` : "Release-ready"}</small>
            </button>;
          })}
        </div>
      </aside>

      {current && annotation && <section className="annotation-workspace">
        <div className="annotation-case-heading">
          <div><span>{current.case_id} · {current.origin_family_id}</span><h2>{current.claim_text}</h2></div>
          <div className={problems.length ? "annotation-status blocked" : "annotation-status ready"}>
            {problems.length ? `${problems.length} checks remaining` : "Ready for release"}
          </div>
        </div>

        {problems.length > 0 && <div className="annotation-problems"><b>Before this case can pass</b><ul>{problems.map((problem) => <li key={problem}>{problem}</li>)}</ul></div>}
        {annotation.annotator_identity.toLowerCase().startsWith("ai-assisted draft") && <div className="annotation-ai-draft">
          <b>AI-prepared suggestion</b>
          <p>Check the dimension, relation, label, state and exact spans. When you agree, replace the annotator identity with your own name. This records human acceptance of the draft; it does not approve the case.</p>
        </div>}

        <div className="annotation-two-column">
          <section className="annotation-evidence-panel">
            <header><span>RETAINED EVIDENCE</span><small>{current.evidence.length} passages</small></header>
            {current.evidence.map((evidence) => {
              const span = annotation.evidence_spans.find((item) => item.evidence_id === evidence.evidence_id);
              return <article key={evidence.evidence_id}>
                <div className="annotation-evidence-title">
                  <label><input type="checkbox" checked={Boolean(span)} onChange={(e) => toggleEvidence(evidence, e.target.checked)} /> Use as gold evidence</label>
                  <a href={evidence.url} target="_blank" rel="noreferrer">Open source ↗</a>
                </div>
                <span>{evidence.evidence_id} · {title(evidence.source_class)}</span>
                <h3>{evidence.title}</h3>
                <blockquote>{evidence.passage}</blockquote>
                {span && <div className="annotation-offsets">
                  <label>Start<input type="number" min={0} max={evidence.passage.length} value={span.start_char} onChange={(e) => updateEvidenceSpan(evidence, "start_char", Number(e.target.value))} /></label>
                  <label>End<input type="number" min={1} max={evidence.passage.length} value={span.end_char} onChange={(e) => updateEvidenceSpan(evidence, "end_char", Number(e.target.value))} /></label>
                  <p>Selected: “{span.quoted_text}”</p>
                </div>}
              </article>;
            })}
          </section>

          <section className="annotation-form-panel">
            <header><span>ANNOTATOR DECISION</span><small>Gold data</small></header>
            <div className="annotation-form-grid">
              <label>Annotator identity<input value={annotation.annotator_identity} onChange={(e) => setAnnotation({ annotator_identity: e.target.value })} /></label>
              <label>Annotation date<input type="date" value={annotation.annotated_on} onChange={(e) => setAnnotation({ annotated_on: e.target.value })} /></label>
              <label>Dimension<select value={annotation.dimension_bucket} onChange={(e) => setAnnotation({ dimension_bucket: e.target.value })}><option value="">Select…</option>{dimensions.map((item) => <option key={item}>{item}</option>)}</select></label>
              <label>Relation<input value={annotation.comparator_or_relation} onChange={(e) => setAnnotation({ comparator_or_relation: e.target.value })} /></label>
              <label>Construction label<select value={annotation.gold_label} onChange={(e) => setAnnotation({ gold_label: e.target.value })}><option value="">Select…</option>{labels.map((item) => <option key={item}>{item}</option>)}</select></label>
              <label>Expected state<select disabled={!["deterministic_constructible", "fallback_eligible"].includes(annotation.gold_label)} value={annotation.expected_verification_state ?? ""} onChange={(e) => setAnnotation({ expected_verification_state: e.target.value || null })}><option value="">Select…</option>{states.map((item) => <option key={item}>{item}</option>)}</select></label>
            </div>

            {annotation.claim_span && <fieldset>
              <legend>Exact claim span</legend>
              <div className="annotation-offsets">
                <label>Start<input type="number" min={0} max={current.claim_text.length} value={annotation.claim_span.start_char} onChange={(e) => updateClaimSpan("start_char", Number(e.target.value))} /></label>
                <label>End<input type="number" min={1} max={current.claim_text.length} value={annotation.claim_span.end_char} onChange={(e) => updateClaimSpan("end_char", Number(e.target.value))} /></label>
                <p>Selected: “{annotation.claim_span.quoted_text}”</p>
              </div>
            </fieldset>}

            <label>Ambiguity notes<textarea placeholder="One note per line" value={annotation.ambiguity_notes.join("\n")} onChange={(e) => setAnnotation({ ambiguity_notes: e.target.value.split("\n").filter(Boolean) })} /></label>
            {!current.annotation && <button className="annotation-approve" onClick={recordReviewedAnnotation}>Record reviewed annotation</button>}

            <div className="annotation-approval">
              <span>DISTINCT APPROVAL</span>
              <div className="annotation-form-grid">
                <label>Approver identity<input value={approval.approver_identity} onChange={(e) => setApproval({ approver_identity: e.target.value })} /></label>
                <label>Approval date<input type="date" value={approval.approved_on} onChange={(e) => setApproval({ approved_on: e.target.value })} /></label>
              </div>
              <label>Approval notes<textarea value={approval.notes.join("\n")} onChange={(e) => setApproval({ notes: e.target.value.split("\n").filter(Boolean) })} /></label>
              <button className="annotation-approve" onClick={approveCurrent}>Record independent approval</button>
              <button className="annotation-return" onClick={() => setApproval({ decision: "return_for_revision" })}>Return for revision</button>
            </div>
          </section>
        </div>
      </section>}

      <aside className="annotation-quota-panel">
        {isReplacementCalibration
          ? <header><span>{isStage6eCalibration ? "V3.6E FRESH CALIBRATION" : isStage6cCalibration ? "V3.6C FRESH CALIBRATION" : "V3.6A REPLACEMENT CALIBRATION"}</span><h2>Isolation controls</h2><p>Twenty fresh cases from at least ten origin families. No target quota may influence a human label, and the original held-out split remains sealed.</p></header>
          : <>
              <header><span>FROZEN SAMPLING POLICY</span><h2>Quota monitor</h2><p>Classify honestly. Replace cases if natural labels cannot meet the frozen plan.</p></header>
              <QuotaGroup title="Construction labels" targets={labelTargets} counts={counts.labelCounts} />
              <QuotaGroup title="Dimensions" targets={dimensionTargets} counts={counts.dimensionCounts} />
            </>}
        <section className="annotation-batch-tools">
          <h3>Batch tools</h3>
          <p>Choose one split. Identity copying never copies labels or decisions.</p>
          <button onClick={copyIdentitiesToSplit}>Copy current identities to split</button>
          <button onClick={approveReviewedSplit}>Approve reviewed split</button>
        </section>
        <div className="annotation-integrity-note"><b>Integrity rule</b><p>{isReplacementCalibration
          ? "Annotation and approval must be completed by distinct people. Export does not execute calibration or expose held-out cases."
          : "Quota pressure is not permission to relabel a case. The final export remains blocked until evidence-based decisions and targets both pass."}</p></div>
      </aside>
    </div>
  </main>;
}

function QuotaGroup({ title: groupTitle, targets, counts }: { title: string; targets: Record<string, number>; counts: Record<string, number> }) {
  return <section className="annotation-quota-group"><h3>{groupTitle}</h3>{Object.entries(targets).map(([key, target]) => {
    const count = counts[key] ?? 0;
    const difference = target - count;
    return <div key={key}>
      <span>{title(key)}</span>
      <i><b style={{ width: `${Math.min(100, count / target * 100)}%` }} /></i>
      <em className={difference === 0 ? "met" : difference > 0 ? "short" : "over"}>{count}/{target} {difference === 0 ? "met" : difference > 0 ? `+${difference} needed` : `${Math.abs(difference)} over`}</em>
    </div>;
  })}</section>;
}
