import httpx
import pytest

from file_fetch_mcp.downloader import DownloadTooLarge, download


@pytest.mark.asyncio
async def test_downloads_stream_and_enforces_limit():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"hello"))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await download("https://example.com/a.txt", client=client, max_bytes=10)
    assert result.data == b"hello"
    assert result.media_type == "text/plain"


@pytest.mark.asyncio
async def test_rejects_large_response_without_trusting_content_length():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"123456"))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(DownloadTooLarge):
            await download("https://example.com/a.txt", client=client, max_bytes=5)
