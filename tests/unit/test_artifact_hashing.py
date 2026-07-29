"""Cross-platform release-artifact hashing."""

import hashlib

from claim_polygraph_ng.evaluation.artifact_hashing import (
    artifact_matches_sha256,
    artifact_sha256,
)


def test_text_hash_is_independent_of_line_ending(tmp_path) -> None:
    unix = tmp_path / "unix.json"
    windows = tmp_path / "windows.json"
    unix.write_bytes(b'{\n  "valid": true\n}\n')
    windows.write_bytes(b'{\r\n  "valid": true\r\n}\r\n')

    assert artifact_sha256(unix) == artifact_sha256(windows)
    assert artifact_matches_sha256(windows, artifact_sha256(unix))


def test_binary_hash_remains_byte_exact(tmp_path) -> None:
    binary = tmp_path / "packet.bin"
    binary.write_bytes(b"a\r\nb")

    assert artifact_sha256(binary) == hashlib.sha256(b"a\r\nb").hexdigest()
