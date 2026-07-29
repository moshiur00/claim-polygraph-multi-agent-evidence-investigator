"""Cross-platform hashing for release-audited repository artifacts."""

import hashlib
from pathlib import Path

_CANONICAL_TEXT_SUFFIXES = frozenset(
    {".json", ".md", ".py", ".toml", ".yaml", ".yml"}
)


def artifact_sha256(path: str | Path) -> str:
    """Hash text with canonical LF endings and binary artifacts byte-for-byte."""
    candidate = Path(path)
    payload = candidate.read_bytes()
    if candidate.suffix.casefold() in _CANONICAL_TEXT_SUFFIXES:
        payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest()


def artifact_matches_sha256(path: str | Path, expected: str) -> bool:
    """Accept legacy raw hashes while new manifests migrate to canonical text."""
    candidate = Path(path)
    raw = candidate.read_bytes()
    return expected in {
        hashlib.sha256(raw).hexdigest(),
        artifact_sha256(candidate),
    }
