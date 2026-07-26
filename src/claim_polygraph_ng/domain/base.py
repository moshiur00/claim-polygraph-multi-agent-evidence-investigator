"""Base configuration for immutable investigation artifacts."""

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Strict base model used by stored and handed-off domain artifacts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
