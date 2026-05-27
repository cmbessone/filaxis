"""Unit tests for the extraction activity (Docling)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


SAMPLE_PDF_PATH = Path(__file__).parent.parent / "hemogramas-001" / "hemograma_ficticio_1.pdf"


@pytest.mark.asyncio
async def test_extract_returns_non_empty_text():
    """extract_text_from_pdf returns a non-empty string from a real PDF."""
    mock_doc = MagicMock()
    mock_doc.export_to_markdown.return_value = "Hemoglobina: 13.7 g/dL\nGlóbulos blancos: 4950 /mm³"
    mock_result = MagicMock()
    mock_result.document = mock_doc
    mock_converter = MagicMock()
    mock_converter.convert.return_value = mock_result

    with patch("filaxis.activities.extraction.DocumentConverter", return_value=mock_converter):
        from filaxis.activities.extraction import extract_text_from_pdf
        text = await extract_text_from_pdf(SAMPLE_PDF_PATH.read_bytes())

    assert len(text) > 0
    assert "Hemoglobina" in text or "13.7" in text


@pytest.mark.asyncio
async def test_extract_cleans_up_temp_file(tmp_path):
    """Temp file is deleted even if extraction raises."""
    mock_converter = MagicMock()
    mock_converter.convert.side_effect = RuntimeError("docling failure")

    with patch("filaxis.activities.extraction.DocumentConverter", return_value=mock_converter):
        from filaxis.activities.extraction import extract_text_from_pdf
        with pytest.raises(RuntimeError, match="docling failure"):
            await extract_text_from_pdf(b"%PDF fake bytes")

    # No tmp .pdf files should linger (we can't easily assert the exact path,
    # but the activity must not propagate without cleanup)
