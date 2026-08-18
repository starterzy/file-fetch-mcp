import httpx
import pytest

from file_fetch_mcp.mineru_client import MinerUResult
from file_fetch_mcp.service import FileFetchService


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
