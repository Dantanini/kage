"""Tests for document/PDF message handling."""

import pytest


class TestBuildDocumentPrompt:
    """Test the extracted build_document_prompt helper."""

    def test_includes_file_path(self):
        from bot import build_document_prompt
        result = build_document_prompt("/tmp/abc123.pdf", "report.pdf", "幫我摘要")
        assert "/tmp/abc123.pdf" in result

    def test_default_caption_when_empty(self):
        from bot import build_document_prompt
        result = build_document_prompt("/tmp/f.pdf", "report.pdf", "")
        assert "report.pdf" in result  # should mention filename as context

    def test_rejects_non_pdf(self):
        from bot import is_supported_document
        assert is_supported_document("report.pdf") is True
        assert is_supported_document("notes.PDF") is True
        assert is_supported_document("photo.jpg") is False
        assert is_supported_document("data.xlsx") is False
        assert is_supported_document(None) is False
