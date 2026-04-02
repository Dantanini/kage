"""Tests for photo message handling — prompt builder and handler logic."""

import pytest


class TestBuildPhotoPrompt:
    """Test the extracted build_photo_prompt helper."""

    def test_includes_image_path(self):
        from bot import build_photo_prompt
        result = build_photo_prompt("/tmp/abc123.jpg", "這是什麼？")
        assert "/tmp/abc123.jpg" in result

    def test_includes_caption(self):
        from bot import build_photo_prompt
        result = build_photo_prompt("/tmp/img.jpg", "幫我翻譯圖片文字")
        assert "幫我翻譯圖片文字" in result

    def test_default_caption_when_none(self):
        from bot import build_photo_prompt
        result = build_photo_prompt("/tmp/img.jpg", None)
        assert "請描述這張圖片" in result

    def test_default_caption_when_empty(self):
        from bot import build_photo_prompt
        result = build_photo_prompt("/tmp/img.jpg", "")
        assert "請描述這張圖片" in result

    def test_mentions_read_tool(self):
        """Prompt should instruct Claude to use Read tool for the image."""
        from bot import build_photo_prompt
        result = build_photo_prompt("/tmp/img.jpg", "test")
        assert "Read" in result or "讀取" in result

    def test_returns_string(self):
        from bot import build_photo_prompt
        result = build_photo_prompt("/tmp/img.jpg", "caption")
        assert isinstance(result, str)
        assert len(result) > 0
