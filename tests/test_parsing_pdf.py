from io import BytesIO

from pypdf import PdfWriter

from src.parsing import parse_document_bytes


def test_blank_pdf_reports_no_extractable_text():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    buffer = BytesIO()
    writer.write(buffer)
    parsed = parse_document_bytes(name="扫描件.pdf", role="reference", data=buffer.getvalue())
    assert parsed.chunks == []
    assert any("未提取到文本" in warning for warning in parsed.warnings)
    assert any("没有可用于证据检索的文本" in warning for warning in parsed.warnings)
