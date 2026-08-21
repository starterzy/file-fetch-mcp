from pathlib import Path

import pytest

from file_fetch_mcp.parsers import UnsupportedFormat, parse_local


SAMPLES = Path(__file__).parents[2] / "test-docs"


def test_parses_sample_docx_to_markdown():
    result = parse_local(SAMPLES / "a76508e9f3054d2fb3a126579a092b49_化工产品购销合同-明日舟山-明日石化.docx")
    assert result.markdown.strip()
    assert result.format == "docx"


def test_parses_sample_xlsx_to_markdown():
    result = parse_local(SAMPLES / "921899196ba048198b80999c9d212ac2_资金定额审批表-5亿控股集团借款（2024年度）.xlsx")
    assert result.markdown.strip()
    assert "|" in result.markdown
    assert result.format == "xlsx"


def test_parses_sample_pdf_to_markdown():
    result = parse_local(SAMPLES / "借款凭证2份.pdf")
    assert result.markdown.strip()
    assert result.format == "pdf"


def test_parses_sample_image_to_markdown_with_ocr_fallback():
    result = parse_local(SAMPLES / "test0.png")
    assert result.markdown.startswith("# Image OCR")
    assert result.format == "image"


def test_wps_without_converter_is_explicitly_unsupported():
    with pytest.raises(UnsupportedFormat):
        parse_local(SAMPLES / "f26d64b5345f4fcbb19c77ba844d4123_不流入房产承诺函-正反打印1份公章法人章法人签字.wps")


def test_user_reported_wps_sample_is_explicitly_unsupported_without_converter():
    """Keep the reported OLE WPS file as a regression fixture for the failure path."""
    with pytest.raises(UnsupportedFormat, match=r"Kingsoft WPS parser is not installed"):
        parse_local(SAMPLES / "c293149d59e14bb8887582df57d1213a.wps")
