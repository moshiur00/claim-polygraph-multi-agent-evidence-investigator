"""Deterministic typed candidates for numerical and temporal construction.

Candidates are exact-span diagnostics. They do not establish an assertion,
verification state, verdict, readiness state, or publication decision.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel

CANDIDATE_EXTRACTION_VERSION = "verification-candidate-extraction-v3"


class VerificationCandidateKind(StrEnum):
    VALUE = "value"
    UNIT = "unit"
    DATE = "date"
    COMPARATOR = "comparator"
    RANK = "rank"
    PROJECTION = "projection"
    STATUS = "status"
    QUANTIFIER = "quantifier"
    MATERIAL_QUALIFIER = "material_qualifier"


class VerificationCandidateGroupKind(StrEnum):
    COMPARISON = "comparison"
    RANGE = "range"
    RANKING = "ranking"
    PROJECTION = "projection"
    COMPOUND_CONDITION = "compound_condition"


class VerificationCandidateDatePrecision(StrEnum):
    YEAR = "year"
    MONTH = "month"
    DAY = "day"


class VerificationCandidate(DomainModel):
    candidate_id: str = Field(pattern=r"^candidate-[0-9]{3}$")
    kind: VerificationCandidateKind
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    quoted_text: str = Field(min_length=1, max_length=500)
    normalized_text: str = Field(min_length=1, max_length=500)
    rule_id: str = Field(pattern=r"^[a-z0-9_]+$")
    material: bool = True
    decimal_value: Decimal | None = None
    decimal_scale: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=100)
    date_value: date | None = None
    date_precision: VerificationCandidateDatePrecision | None = None
    ordinal_rank: int | None = Field(default=None, ge=1)
    relation: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_offsets(self) -> VerificationCandidate:
        if self.end_char <= self.start_char:
            raise ValueError("candidate end must follow its start")
        if self.kind is VerificationCandidateKind.VALUE and (
            self.decimal_value is None or self.decimal_scale is None
        ):
            raise ValueError("value candidates require an exact decimal and scale")
        if self.kind is VerificationCandidateKind.UNIT and self.unit is None:
            raise ValueError("unit candidates require a normalized unit")
        if self.kind is VerificationCandidateKind.DATE and (
            self.date_value is None or self.date_precision is None
        ):
            raise ValueError("date candidates require a value and precision")
        if self.kind is VerificationCandidateKind.RANK and self.ordinal_rank is None:
            raise ValueError("rank candidates require an ordinal")
        if (
            self.kind
            in {
                VerificationCandidateKind.COMPARATOR,
                VerificationCandidateKind.PROJECTION,
                VerificationCandidateKind.STATUS,
                VerificationCandidateKind.QUANTIFIER,
                VerificationCandidateKind.MATERIAL_QUALIFIER,
            }
            and self.relation is None
        ):
            raise ValueError(f"{self.kind.value} candidates require a typed relation")
        return self


class VerificationCandidateGroup(DomainModel):
    group_id: str = Field(pattern=r"^group-[0-9]{3}$")
    kind: VerificationCandidateGroupKind
    candidate_ids: tuple[str, ...] = Field(min_length=2)
    rule_id: str = Field(pattern=r"^[a-z0-9_]+$")


class VerificationCandidateExtraction(DomainModel):
    version: str = CANDIDATE_EXTRACTION_VERSION
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text_length: int = Field(ge=1, le=10_000)
    candidates: tuple[VerificationCandidate, ...]
    groups: tuple[VerificationCandidateGroup, ...] = ()
    requires_multi_assertion: bool = False
    limitations: tuple[str, ...] = (
        "Candidates are lexical diagnostics, not verified operands or proof.",
        "A candidate must still be bound to approved evidence and validated.",
    )

    @model_validator(mode="after")
    def validate_packet(self) -> VerificationCandidateExtraction:
        ids = [item.candidate_id for item in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate IDs must be unique")
        known = set(ids)
        for group in self.groups:
            if not set(group.candidate_ids).issubset(known):
                raise ValueError("candidate group references an unknown candidate")
            if len(group.candidate_ids) != len(set(group.candidate_ids)):
                raise ValueError("candidate group IDs must be unique")
        return self


_NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}
_VALUE = re.compile(
    r"(?<![\w-])(?:[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|"
    r"zero|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"(?:\s*(?:million|billion|trillion))?(?:\s*%)?",
    re.IGNORECASE,
)
_UNIT = re.compile(
    r"(?:°\s*[CFK]|degrees?\s+(?:Celsius|Fahrenheit|Kelvin)|"
    r"hectopascals?|hPa|kPa|pascals?|psi|pounds?\s+per\s+square\s+inch|"
    r"percent(?:age)?|%|hours?|days?|years?|months?|minutes?|seconds?|"
    r"kilomet(?:er|re)s?|meters?|metres?|miles?|feet|foot|inches?|"
    r"kilograms?|grams?|tonnes?|dollars?|euros?|vehicles?|people|members?|"
    r"countries|territories|infections|participants|bones)",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2})-[01][0-9]-[0-3][0-9]\b")
_NAMED_DATE = re.compile(
    r"\b(?:(?:[0-3]?\d)\s+)?"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"(?:\s+(?:[0-3]?\d),?)?\s+(?:1[0-9]{3}|20[0-9]{2})\b",
    re.IGNORECASE,
)
_YEAR = re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2})\b")

_COMPARATORS = (
    ("between", r"\bbetween\b"),
    ("range_from_to", r"\bfrom\b(?=.{0,80}\bto\b)"),
    ("greater_than_or_equal", r"\b(?:at least|no less than)\b"),
    ("less_than_or_equal", r"\b(?:at most|no more than)\b"),
    (
        "greater_than",
        r"\b(?:more than|greater than|higher than|longer than|hotter than|above|exceeds?)\b",
    ),
    ("less_than", r"\b(?:less than|lower than|shorter than|colder than|below)\b"),
    ("multiplicative", r"\b(?:twice|double|half|hundreds?\s+of\s+times|\d+(?:\.\d+)?\s+times)\b"),
    ("approximately_equal", r"\b(?:about|approximately|around|almost|roughly)\b"),
    ("equal", r"\b(?:exactly|equals?|equal to|is)\b"),
)
_RANK_WORDS = {
    "first": "1",
    "second": "2",
    "third": "3",
    "fourth": "4",
    "fifth": "5",
    "sixth": "6",
    "seventh": "7",
    "eighth": "8",
    "ninth": "9",
    "tenth": "10",
}
_RANK = re.compile(
    r"\b(?:(?P<number>\d+)(?:st|nd|rd|th)|(?P<word>"
    + "|".join(_RANK_WORDS)
    + r"))(?:\s*-\s*|\s+)(?:largest|smallest|highest|lowest|ranked)\b",
    re.IGNORECASE,
)
_SUPERLATIVE_RANK = re.compile(
    r"\b(?:largest|smallest|highest|lowest|tallest|farthest)\b",
    re.IGNORECASE,
)
_PROJECTION = (
    ("projected", r"\bproject(?:ed|ion)?\b"),
    ("forecast", r"\bforecast(?:ed)?\b"),
    ("expected", r"\bexpected\s+to\b"),
    ("estimated", r"\bestimated\b"),
)
_STATUS = (
    ("inactive", r"\b(?:no longer(?:\s+active)?|inactive|ended|ceased|terminated)\b"),
    ("active", r"\b(?:still|currently|active|ongoing)\b"),
    ("started", r"\b(?:began|started|founded|established|created|launched)\b"),
    ("absence", r"\b(?:never|no|none|zero|does not|do not|without)\b"),
)
_QUANTIFIER = (
    ("universal", r"\b(?:every|all|always|each)\b"),
    ("negative_universal", r"\bnever\b"),
    ("only", r"\bonly\b"),
    ("more_than", r"\bmore than\b"),
)
_QUALIFIER = (
    ("exact", r"\bexactly\b"),
    ("approximate", r"\b(?:about|approximately|around|almost|roughly)\b"),
    ("uncertain", r"\b(?:estimated|reported|nominal|typical(?:ly)?)\b"),
    ("current", r"\b(?:currently|today|now|still|as of|no longer)\b"),
    ("scope", r"\b(?:total|ordinary|average|mean|global|worldwide)\b"),
    ("condition", r"\b(?:during|after|before|by|under|for at least|for more than)\b"),
)


def extract_verification_candidates(text: str) -> VerificationCandidateExtraction:
    """Extract stable exact-span candidates without interpreting claim truth."""
    if not 1 <= len(text) <= 10_000:
        raise ValueError("candidate extraction text must contain 1 to 10,000 characters")
    raw: list[tuple[VerificationCandidateKind, int, int, str, str, str]] = []

    def add(
        kind: VerificationCandidateKind,
        match: re.Match[str],
        normalized: str,
        rule_id: str,
    ) -> None:
        raw.append(
            (
                kind,
                match.start(),
                match.end(),
                match.group(0),
                normalized,
                rule_id,
            )
        )

    for match in _VALUE.finditer(text):
        normalized = match.group(0).casefold().replace(",", "").replace(" ", "")
        add(VerificationCandidateKind.VALUE, match, normalized, "explicit_value")
    for match in _UNIT.finditer(text):
        add(
            VerificationCandidateKind.UNIT,
            match,
            _normalize_unit(match.group(0)),
            "explicit_unit",
        )
    date_spans: set[tuple[int, int]] = set()
    for pattern, rule in (
        (_ISO_DATE, "iso_date"),
        (_NAMED_DATE, "named_date"),
        (_YEAR, "year_date"),
    ):
        for match in pattern.finditer(text):
            if any(start <= match.start() and match.end() <= end for start, end in date_spans):
                continue
            date_spans.add((match.start(), match.end()))
            add(
                VerificationCandidateKind.DATE,
                match,
                match.group(0).casefold(),
                rule,
            )
    for normalized, pattern in _COMPARATORS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            add(VerificationCandidateKind.COMPARATOR, match, normalized, f"comparator_{normalized}")
    for match in _RANK.finditer(text):
        normalized = match.group("number") or _RANK_WORDS[match.group("word").casefold()]
        add(VerificationCandidateKind.RANK, match, normalized, "ordinal_rank")
    for match in _SUPERLATIVE_RANK.finditer(text):
        add(VerificationCandidateKind.RANK, match, "1", "implicit_first_rank")
    for normalized, pattern in _PROJECTION:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            add(VerificationCandidateKind.PROJECTION, match, normalized, f"projection_{normalized}")
    for normalized, pattern in _STATUS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            add(VerificationCandidateKind.STATUS, match, normalized, f"status_{normalized}")
    for normalized, pattern in _QUANTIFIER:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            add(VerificationCandidateKind.QUANTIFIER, match, normalized, f"quantifier_{normalized}")
    for normalized, pattern in _QUALIFIER:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            add(
                VerificationCandidateKind.MATERIAL_QUALIFIER,
                match,
                normalized,
                f"qualifier_{normalized}",
            )

    raw = [
        item
        for item in raw
        if not (
            item[0] is VerificationCandidateKind.STATUS
            and any(
                other[0] is item[0]
                and other[1] <= item[1]
                and item[2] <= other[2]
                and (other[2] - other[1]) > (item[2] - item[1])
                for other in raw
            )
        )
    ]
    unique = {
        (kind, start, end, normalized, rule): (
            quoted,
            not (
                kind is VerificationCandidateKind.VALUE
                and any(
                    date_start <= start and end <= date_end for date_start, date_end in date_spans
                )
            ),
        )
        for kind, start, end, quoted, normalized, rule in raw
    }
    ordered = sorted(
        (
            (kind, start, end, quoted, normalized, rule, material)
            for (kind, start, end, normalized, rule), (quoted, material) in unique.items()
        ),
        key=lambda item: (item[1], item[2], item[0].value, item[5]),
    )
    candidates = tuple(
        VerificationCandidate(
            candidate_id=f"candidate-{index:03d}",
            kind=kind,
            start_char=start,
            end_char=end,
            quoted_text=quoted,
            normalized_text=normalized,
            rule_id=rule,
            material=material,
            **_typed_fields(kind, quoted, normalized, rule),
        )
        for index, (kind, start, end, quoted, normalized, rule, material) in enumerate(ordered, 1)
    )
    groups = _candidate_groups(text, candidates)
    packet = VerificationCandidateExtraction(
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        text_length=len(text),
        candidates=candidates,
        groups=groups,
        requires_multi_assertion=any(
            group.kind is VerificationCandidateGroupKind.COMPOUND_CONDITION for group in groups
        ),
    )
    for candidate in packet.candidates:
        if text[candidate.start_char : candidate.end_char] != candidate.quoted_text:
            raise AssertionError("candidate offsets do not reproduce exact text")
    return packet


def _candidate_groups(
    text: str,
    candidates: tuple[VerificationCandidate, ...],
) -> tuple[VerificationCandidateGroup, ...]:
    by_kind = {
        kind: tuple(item for item in candidates if item.kind is kind)
        for kind in VerificationCandidateKind
    }
    groups: list[tuple[VerificationCandidateGroupKind, tuple[str, ...], str]] = []
    # Digits inside a recognized date remain available as exact-span diagnostics,
    # but they must never become numerical operands or assertion anchors.
    values = tuple(item for item in by_kind[VerificationCandidateKind.VALUE] if item.material)
    comparators = by_kind[VerificationCandidateKind.COMPARATOR]
    dates = by_kind[VerificationCandidateKind.DATE]
    ranks = by_kind[VerificationCandidateKind.RANK]
    projections = by_kind[VerificationCandidateKind.PROJECTION]
    units = by_kind[VerificationCandidateKind.UNIT]
    qualifiers = by_kind[VerificationCandidateKind.MATERIAL_QUALIFIER]
    if ranks:
        members = tuple(item.candidate_id for item in (*ranks, *dates, *values))
        if len(members) >= 2:
            groups.append((VerificationCandidateGroupKind.RANKING, members, "rank_with_context"))
    if projections and len(values) >= 2:
        members = tuple(item.candidate_id for item in (*projections, *values, *dates))
        groups.append(
            (VerificationCandidateGroupKind.PROJECTION, members, "projected_value_change")
        )
    if len(values) >= 2 and comparators:
        kind = (
            VerificationCandidateGroupKind.RANGE
            if any(item.normalized_text in {"between", "range_from_to"} for item in comparators)
            else VerificationCandidateGroupKind.COMPARISON
        )
        groups.append(
            (
                kind,
                tuple(item.candidate_id for item in (*values, *comparators, *units)),
                "multi_value_relation",
            )
        )
    normalized = f" {text.casefold()} "
    condition_markers = (" for ", " during ", " after ", " before ", " when ", " if ")
    if (
        len(values) >= 2
        and any(marker in normalized for marker in condition_markers)
        and (comparators or qualifiers)
    ):
        members = tuple(
            item.candidate_id for item in (*values, *comparators, *units, *qualifiers, *dates)
        )
        groups.append(
            (
                VerificationCandidateGroupKind.COMPOUND_CONDITION,
                tuple(dict.fromkeys(members)),
                "multiple_material_conditions",
            )
        )
    return tuple(
        VerificationCandidateGroup(
            group_id=f"group-{index:03d}",
            kind=kind,
            candidate_ids=tuple(dict.fromkeys(members)),
            rule_id=rule,
        )
        for index, (kind, members, rule) in enumerate(groups, 1)
        if len(set(members)) >= 2
    )


def _normalize_unit(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.casefold().strip())
    aliases = {
        "%": "percent",
        "hpa": "hectopascal",
        "hours": "hour",
        "days": "day",
        "years": "year",
        "months": "month",
        "minutes": "minute",
        "seconds": "second",
        "people": "person",
        "countries": "country",
        "territories": "territory",
        "inches": "inch",
    }
    return aliases.get(normalized, normalized.rstrip("s"))


def _typed_fields(
    kind: VerificationCandidateKind,
    quoted: str,
    normalized: str,
    rule: str,
) -> dict[str, object]:
    if kind is VerificationCandidateKind.VALUE:
        compact = quoted.casefold().replace(",", "").replace("%", "").strip()
        scale = Decimal(1)
        for suffix, candidate_scale in (
            ("trillion", Decimal("1000000000000")),
            ("billion", Decimal("1000000000")),
            ("million", Decimal("1000000")),
        ):
            if compact.endswith(suffix):
                compact = compact[: -len(suffix)].strip()
                scale = candidate_scale
                break
        compact = _NUMBER_WORDS.get(compact, compact)
        return {"decimal_value": Decimal(compact), "decimal_scale": scale}
    if kind is VerificationCandidateKind.UNIT:
        return {"unit": normalized}
    if kind is VerificationCandidateKind.DATE:
        value, precision = _parse_candidate_date(quoted, rule)
        return {"date_value": value, "date_precision": precision}
    if kind is VerificationCandidateKind.RANK:
        return {"ordinal_rank": int(normalized)}
    return {"relation": normalized}


def _parse_candidate_date(
    quoted: str, rule: str
) -> tuple[date, VerificationCandidateDatePrecision]:
    if rule == "year_date":
        return date(int(quoted), 1, 1), VerificationCandidateDatePrecision.YEAR
    if rule == "iso_date":
        return (
            date.fromisoformat(quoted),
            VerificationCandidateDatePrecision.DAY,
        )
    normalized = re.sub(r"\s+", " ", quoted.replace(",", " ").strip())
    formats = (
        ("%d %B %Y", VerificationCandidateDatePrecision.DAY),
        ("%d %b %Y", VerificationCandidateDatePrecision.DAY),
        ("%B %d %Y", VerificationCandidateDatePrecision.DAY),
        ("%b %d %Y", VerificationCandidateDatePrecision.DAY),
        ("%B %Y", VerificationCandidateDatePrecision.MONTH),
        ("%b %Y", VerificationCandidateDatePrecision.MONTH),
    )
    for date_format, precision in formats:
        try:
            return datetime.strptime(normalized, date_format).date(), precision
        except ValueError:
            continue
    raise ValueError(f"unsupported deterministic date form: {quoted}")
