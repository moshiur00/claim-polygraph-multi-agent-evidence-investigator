"""Enumerations shared by investigation artifacts."""

from enum import StrEnum


class ClaimType(StrEnum):
    """Broad claim shapes used for routing and evaluation."""

    FACTUAL = "factual"
    NUMERICAL = "numerical"
    TEMPORAL = "temporal"
    COMPARATIVE = "comparative"
    CAUSAL = "causal"
    SCIENTIFIC = "scientific"
    LEGAL = "legal"
    HISTORICAL = "historical"
    PREDICTION = "prediction"
    OTHER = "other"


class ComponentStatus(StrEnum):
    """Durable outcome for one material claim component."""

    PLANNED = "planned"
    COMPLETED = "completed"
    UNRESOLVED = "unresolved"
    FAILED = "failed"


class ResearchPath(StrEnum):
    """Available evidence-research paths."""

    PRIMARY = "primary"
    GENERAL = "general"
    FACT_CHECK = "fact_check"
    ACADEMIC = "academic"
    CONTRADICTION = "contradiction"


class SourceType(StrEnum):
    """Source categories used by planning and quality assessment."""

    OFFICIAL = "official"
    PRIMARY_DOCUMENT = "primary_document"
    DATASET = "dataset"
    LAW_OR_REGULATION = "law_or_regulation"
    ACADEMIC = "academic"
    NEWS = "news"
    FACT_CHECK = "fact_check"
    ORGANIZATION = "organization"
    EXPERT = "expert"
    OTHER = "other"


class DistributionMedium(StrEnum):
    """How material was distributed, independently of who authored it."""

    UNKNOWN = "unknown"
    WEB_PAGE = "web_page"
    SOCIAL_PLATFORM = "social_platform"
    DOCUMENT = "document"
    DATASET_OR_API = "dataset_or_api"
    BROADCAST = "broadcast"


class SocialAccountType(StrEnum):
    """The represented account owner; this does not establish authority."""

    UNKNOWN = "unknown"
    INDIVIDUAL = "individual"
    INSTITUTION = "institution"
    GOVERNMENT = "government"
    ACADEMIC_INSTITUTION = "academic_institution"
    NEWS_ORGANIZATION = "news_organization"
    AUTOMATED = "automated"


class SocialAuthenticityStatus(StrEnum):
    """Recorded authenticity state for a social account or item."""

    UNKNOWN = "unknown"
    UNVERIFIED = "unverified"
    AUTHENTICATED = "authenticated"
    DISPUTED = "disputed"


class SocialPostType(StrEnum):
    """Structural type of social-media material."""

    UNKNOWN = "unknown"
    ORIGINAL = "original"
    REPLY = "reply"
    REPOST = "repost"
    QUOTE = "quote"
    SCREENSHOT = "screenshot"
    LINK_SHARE = "link_share"


class SocialPlatform(StrEnum):
    """Deterministically recognized public social URL families."""

    X = "x"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    THREADS = "threads"
    LINKEDIN = "linkedin"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    BLUESKY = "bluesky"
    REDDIT = "reddit"
    MASTODON = "mastodon"


class SocialUrlKind(StrEnum):
    """What a recognized social URL locates without fetching it."""

    POST = "post"
    ACCOUNT = "account"
    COMMUNITY = "community"
    UNKNOWN = "unknown"


class SocialAuthenticityEvidenceType(StrEnum):
    """Recorded basis used to authenticate an account or social item."""

    OFFICIAL_WEBSITE_LINK = "official_website_link"
    PLATFORM_ASSERTION = "platform_assertion"
    CROSS_REFERENCED_IDENTIFIER = "cross_referenced_identifier"
    CRYPTOGRAPHIC_SIGNATURE = "cryptographic_signature"
    RELIABLE_ARCHIVE = "reliable_archive"
    HUMAN_VERIFICATION = "human_verification"


class SocialCaptureMethod(StrEnum):
    """How social material entered the evidence workflow."""

    UNKNOWN = "unknown"
    SEARCH_RESULT_SNIPPET = "search_result_snippet"
    DIRECT_PUBLIC_PAGE = "direct_public_page"
    PROVIDER_API = "provider_api"
    RELIABLE_ARCHIVE = "reliable_archive"
    SCREENSHOT = "screenshot"
    COPIED_TEXT = "copied_text"


class SocialContentOriginStatus(StrEnum):
    """Availability and origin state of the represented social content."""

    UNKNOWN = "unknown"
    ORIGINAL_ACCESSIBLE = "original_accessible"
    ORIGINAL_UNAVAILABLE = "original_unavailable"
    ARCHIVED_COPY = "archived_copy"
    SCREENSHOT_ONLY = "screenshot_only"
    COPIED_TEXT_ONLY = "copied_text_only"


class SocialAttributionScope(StrEnum):
    """The narrow proposition attributable to a social item."""

    UNSPECIFIED = "unspecified"
    PUBLICATION_EXISTENCE = "publication_existence"
    ATTRIBUTED_STATEMENT = "attributed_statement"
    EYEWITNESS_OBSERVATION = "eyewitness_observation"
    INSTITUTIONAL_ANNOUNCEMENT = "institutional_announcement"
    LINKED_SOURCE_DISCOVERY = "linked_source_discovery"


class SocialSourceRelationship(StrEnum):
    """Relationship from a social item to its underlying or prior source."""

    UNDERLYING_RECORD = "underlying_record"
    REPOST_OF = "repost_of"
    QUOTES = "quotes"
    SCREENSHOT_OF = "screenshot_of"
    LINKS_TO = "links_to"


class EvidentiaryUse(StrEnum):
    """The bounded role an item may play in an investigation."""

    UNSPECIFIED = "unspecified"
    DECISIVE = "decisive"
    QUALIFIED_OBSERVATION = "qualified_observation"
    ATTRIBUTED_STATEMENT = "attributed_statement"
    CONTEXT = "context"
    DISCOVERY_LEAD = "discovery_lead"
    EXCLUDED = "excluded"


class EvidenceEligibilityDecision(StrEnum):
    """Deterministic social-evidence eligibility outcome."""

    UNKNOWN = "unknown"
    ELIGIBLE = "eligible"
    CONDITIONAL = "conditional"
    INELIGIBLE = "ineligible"


class EvidenceStance(StrEnum):
    """Relationship between an evidence passage and a claim."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    CONTEXT = "context"
    IRRELEVANT = "irrelevant"


class ExtractionStatus(StrEnum):
    """Outcome of extracting evidence from a source."""

    EXTRACTED = "extracted"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


class RightsStatus(StrEnum):
    """Recorded copyright or reuse status; unknown is the safe default."""

    UNKNOWN = "unknown"
    LICENSED = "licensed"
    PUBLIC_DOMAIN = "public_domain"
    PERMISSION_CONFIRMED = "permission_confirmed"
    LEGAL_EXCEPTION_ASSERTED = "legal_exception_asserted"


class ContentRetention(StrEnum):
    """How much retrieved source content may be stored durably."""

    METADATA_ONLY = "metadata_only"
    EVIDENCE_PASSAGES_ONLY = "evidence_passages_only"


class VerdictLabel(StrEnum):
    """Nuanced verdict taxonomy."""

    SUPPORTED = "supported"
    MOSTLY_SUPPORTED = "mostly_supported"
    MIXED = "mixed"
    MISLEADING = "misleading"
    OUTDATED = "outdated"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"


class SupportLevel(StrEnum):
    """Sentence-level citation support."""

    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"


class AuditIssue(StrEnum):
    """Material citation and report issues."""

    MISSING_CITATION = "missing_citation"
    CITATION_MISMATCH = "citation_mismatch"
    PARTIAL_SUPPORT = "partial_support"
    NUMERICAL_MISMATCH = "numerical_mismatch"
    TEMPORAL_MISMATCH = "temporal_mismatch"
    OVERSTATEMENT = "overstatement"
    SOURCE_NOT_APPROVED = "source_not_approved"
