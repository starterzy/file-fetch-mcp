import httpx
import pytest

from file_fetch_mcp.mineru_client import MinerUResult
from file_fetch_mcp.service import FileFetchService
from file_fetch_mcp.models import ParseResult


@pytest.mark.asyncio
async def test_service_returns_mineru_markdown():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"ignored"))
    async with httpx.AsyncClient(transport=transport) as http:
        class FakeMinerU:
            async def parse(self, data, filename, media_type):
                return MinerUResult(markdown="# from mineru", parser="mineru")

        service = FileFetchService(http=http, mineru=FakeMinerU())
        result = await service.extract("https://example.com/a.pdf")
    assert result.markdown == "# from mineru"
    assert result.parser == "mineru"


@pytest.mark.asyncio
async def test_service_falls_back_when_mineru_fails():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"plain fallback"))
    async with httpx.AsyncClient(transport=transport) as http:
        class BrokenMinerU:
            async def parse(self, data, filename, media_type):
                raise RuntimeError("MinerU unavailable")

        service = FileFetchService(http=http, mineru=BrokenMinerU())
        result = await service.extract("https://example.com/a.txt")
    assert "plain fallback" in result.markdown
    assert result.parser == "local"
    assert result.warnings


@pytest.mark.asyncio
@pytest.mark.parametrize("filename, content, expected_format", [
    ("sample.xml", b"<root>xml</root>", "xml"),
    ("sample.txt", "plain text".encode(), "txt"),
])
async def test_service_parses_xml_and_txt_without_mineru(filename, content, expected_format):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=content))

    class FailingMinerU:
        async def parse(self, data, filename, media_type):
            raise AssertionError("plain text formats must not call MinerU")

    async with httpx.AsyncClient(transport=transport) as http:
        result = await FileFetchService(http=http, mineru=FailingMinerU()).extract(
            f"https://example.com/{filename}"
        )

    assert result.format == expected_format
    assert result.markdown
    assert result.parser == "local"


@pytest.mark.asyncio
async def test_service_parses_zip_entries_without_mineru():
    import io
    from zipfile import ZipFile

    payload = io.BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("one.txt", "one")
        archive.writestr("two.xml", "<two/>")
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=payload.getvalue()))

    class FailingMinerU:
        async def parse(self, data, filename, media_type):
            raise AssertionError("ZIP entries must be parsed locally")

    async with httpx.AsyncClient(transport=transport) as http:
        result = await FileFetchService(http=http, mineru=FailingMinerU()).extract(
            "https://example.com/bundle.zip"
        )

    assert result.format == "zip"
    assert result.markdown == "# one.txt\n\none\n\n# two.xml\n\n<two/>"
    assert result.parser == "local"


@pytest.mark.asyncio
async def test_service_routes_zip_document_entries_through_mineru():
    import io
    from zipfile import ZipFile

    payload = io.BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("contract.pdf", b"pdf bytes")
        archive.writestr("minutes.docx", b"docx bytes")
        archive.writestr("notes.txt", "plain notes")
    calls = []

    class FakeMinerU:
        async def parse(self, data, filename, media_type):
            calls.append((data, filename, media_type))
            return MinerUResult(markdown=f"# parsed {filename}")

    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=payload.getvalue()))
    async with httpx.AsyncClient(transport=transport) as http:
        result = await FileFetchService(http=http, mineru=FakeMinerU()).extract(
            "https://example.com/bundle.zip"
        )

    assert calls == [
        (b"pdf bytes", "contract.pdf", "application/pdf"),
        (b"docx bytes", "minutes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ]
    assert "# contract.pdf\n\n# parsed contract.pdf" in result.markdown
    assert "# minutes.docx\n\n# parsed minutes.docx" in result.markdown
    assert "# notes.txt\n\nplain notes" in result.markdown
    assert result.format == "zip"
    assert result.parser == "zip+mixed"


@pytest.mark.asyncio
async def test_service_converts_wps_to_pdf_before_mineru(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"wps bytes"))
    calls = []

    async def parse_wps(data, filename, media_type):
        calls.append((data, filename, media_type))
        return MinerUResult(markdown="# from converted WPS")

    monkeypatch.setattr("file_fetch_mcp.service.convert_to_pdf", lambda data, filename: b"%PDF-1.7 converted")
    async with httpx.AsyncClient(transport=transport) as http:
        class FakeMinerU:
            parse = parse_wps

        service = FileFetchService(http=http, mineru=FakeMinerU())
        result = await service.extract("https://example.com/c293149d59e14bb8887582df57d1213a.wps")

    assert result.parser == "wps-to-pdf+mineru"
    assert result.format == "wps"
    assert calls == [(b"%PDF-1.7 converted", "c293149d59e14bb8887582df57d1213a.pdf", "application/pdf")]


@pytest.mark.asyncio
async def test_service_uses_local_wps_package_when_conversion_or_mineru_fails(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"wps bytes"))

    def local_wps_parser(path):
        assert path.endswith(".wps")
        return ParseResult(markdown="# from local WPS package", format="wps", parser="wps-local")

    monkeypatch.setenv("WPS_LOCAL_PARSER", "tests.test_service:local_wps_parser")
    monkeypatch.setattr("file_fetch_mcp.service.convert_to_pdf", lambda data, filename: (_ for _ in ()).throw(RuntimeError("converter down")))
    async with httpx.AsyncClient(transport=transport) as http:
        class BrokenMinerU:
            async def parse(self, data, filename, media_type):
                raise RuntimeError("MinerU unavailable")

        service = FileFetchService(http=http, mineru=BrokenMinerU())
        result = await service.extract("https://example.com/c293149d59e14bb8887582df57d1213a.wps")

    assert result.parser == "wps-local"
    assert result.markdown == "# from local WPS package"
    assert result.warnings == ["WPS PDF/MinerU fallback: RuntimeError"]
