from pathlib import Path

import pytest

from file_fetch_mcp.parsers import UnsupportedFormat, parse_local


def test_legacy_doc_is_explicit_when_converter_is_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("LEGACY_DOC_PARSER", raising=False)
    monkeypatch.setattr("file_fetch_mcp.parsers.shutil.which", lambda name: None)
    path = tmp_path / "legacy.doc"
    path.write_bytes(b"not a real doc")
    with pytest.raises(UnsupportedFormat, match="legacy .doc"):
        parse_local(path)
