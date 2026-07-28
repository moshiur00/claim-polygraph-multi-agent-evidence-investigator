"""Provider protocols and deterministic development adapters."""

from claim_polygraph_ng.providers.base import (
    AcademicSearchProvider,
    FactCheckSearchProvider,
    SearchProvider,
    StructuredModelProvider,
)
from claim_polygraph_ng.providers.factcheck import GoogleFactCheckSearchProvider
from claim_polygraph_ng.providers.mock import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)
from claim_polygraph_ng.providers.ollama import (
    ModelOutputError,
    ModelProviderError,
    ModelUnavailableError,
    OllamaStructuredModelProvider,
)
from claim_polygraph_ng.providers.openai import OpenAIStructuredModelProvider
from claim_polygraph_ng.providers.pubmed import PubMedAcademicSearchProvider
from claim_polygraph_ng.providers.searxng import (
    SearchProviderError,
    SearXNGSearchProvider,
)
from claim_polygraph_ng.providers.semantic_scholar import (
    SemanticScholarAcademicSearchProvider,
)
from claim_polygraph_ng.providers.serpapi import SerpAPISearchProvider

__all__ = [
    "AcademicSearchProvider",
    "DeterministicModelProvider",
    "DeterministicSearchProvider",
    "FactCheckSearchProvider",
    "GoogleFactCheckSearchProvider",
    "ModelOutputError",
    "ModelProviderError",
    "ModelUnavailableError",
    "OllamaStructuredModelProvider",
    "OpenAIStructuredModelProvider",
    "PubMedAcademicSearchProvider",
    "SearXNGSearchProvider",
    "SearchProvider",
    "SearchProviderError",
    "SemanticScholarAcademicSearchProvider",
    "SerpAPISearchProvider",
    "StructuredModelProvider",
]
