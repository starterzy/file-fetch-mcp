import httpx
import pytest

from file_fetch_mcp.mineru_client import MinerUClient, MinerUError


@pytest.mark.asyncio
async def test_mineru_client_polls_and_returns_markdown():
    calls = []
    request_bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/file_parse":
            request_bodies.append(request.content)
            return httpx.Response(200, json={"task_id": "t1"})
        if request.url.path == "/tasks/t1":
            return httpx.Response(200, json={"state": "done"})
        return httpx.Response(200, json={"markdown": "# parsed"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = MinerUClient("https://mineru.internal", http=http, poll_interval=0)
        result = await client.parse(b"%PDF", "sample.pdf", "application/pdf")
    assert result.markdown == "# parsed"
    assert calls == ["/file_parse", "/tasks/t1", "/tasks/t1/result"]
    assert b'name="backend"' in request_bodies[0]
    assert b'pipeline' in request_bodies[0]
    assert b'name="url"' not in request_bodies[0]


@pytest.mark.asyncio
async def test_mineru_client_sends_configured_vlm_url():
    request_bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_bodies.append(request.content)
        return httpx.Response(200, json={"markdown": "# parsed"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = MinerUClient("https://mineru.internal", http=http, backend="vlm-http-client", vlm_url="http://vllm.internal:30000")
        await client.parse(b"%PDF", "sample.pdf", "application/pdf")
    assert b'vlm-http-client' in request_bodies[0]
    assert b'http://vllm.internal:30000' in request_bodies[0]


def test_mineru_client_reads_v34_results_payload():
    result = MinerUClient._result_from_payload({"results": {"sample.pdf": {"md_content": "# nested"}}})
    assert result.markdown == "# nested"


@pytest.mark.asyncio
async def test_mineru_client_raises_on_failed_task():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/file_parse":
            return httpx.Response(200, json={"task_id": "t1"})
        return httpx.Response(200, json={"state": "failed", "error": "bad file"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = MinerUClient("https://mineru.internal", http=http, poll_interval=0)
        with pytest.raises(MinerUError, match="bad file"):
            await client.parse(b"bad", "sample.pdf", "application/pdf")
