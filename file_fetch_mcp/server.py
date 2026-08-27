import asyncio
import json
import os
import time
from dataclasses import dataclass
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from .service import FileFetchService

mcp = FastMCP(
    "file-fetch-mcp",
    host=os.getenv("MCP_HTTP_HOST", "127.0.0.1"),
    port=int(os.getenv("MCP_HTTP_PORT", "8000")),
    streamable_http_path="/mcp",
)
service = FileFetchService(
    max_bytes=int(os.getenv("DOWNLOAD_MAX_BYTES", str(50 * 1024 * 1024))),
    allow_private_urls=os.getenv("ALLOW_PRIVATE_NETWORK_URLS", "false").lower() in {"1", "true", "yes", "on"},
)
_async_jobs: dict[str, "AsyncParseJob"] = {}
_async_job_ttl_seconds = int(os.getenv("ASYNC_PARSE_JOB_TTL_SECONDS", "3600"))
_async_job_semaphore = asyncio.Semaphore(int(os.getenv("ASYNC_PARSE_MAX_CONCURRENT", "2")))


@dataclass
class AsyncParseJob:
    task_id: str
    status: str = "queued"
    created_at: float = 0.0
    updated_at: float = 0.0
    result: dict | None = None
    error: str | None = None


def _cleanup_async_jobs() -> None:
    expire_before = time.monotonic() - _async_job_ttl_seconds
    for task_id, job in list(_async_jobs.items()):
        if job.status in {"success", "failed"} and job.updated_at < expire_before:
            _async_jobs.pop(task_id, None)


async def _run_async_parse(job: AsyncParseJob, url: str, file_name: str | None, max_chars: int) -> None:
    async with _async_job_semaphore:
        job.status = "processing"
        job.updated_at = time.monotonic()
        try:
            result = await service.extract(url, file_name=file_name, max_chars=max_chars)
            job.result = result.as_dict()
            job.status = "success"
        except Exception as exc:
            job.error = f"{type(exc).__name__}: {exc}"
            job.status = "failed"
        finally:
            job.updated_at = time.monotonic()


@mcp.tool()
async def extract_file_content(url: str, file_name: str | None = None, max_chars: int = 50_000) -> str:
    """Download an anonymous HTTP/HTTPS file URL and return MinerU-style Markdown content."""
    result = await service.extract(url, file_name=file_name, max_chars=max_chars)
    if result.warnings:
        return result.markdown + "\n\n" + "\n".join(f"> Warning: {warning}" for warning in result.warnings)
    return result.markdown


@mcp.tool()
async def submit_file_parse(url: str, file_name: str | None = None, max_chars: int = 50_000) -> str:
    """Submit a file extraction task and return immediately with a task_id."""
    _cleanup_async_jobs()
    task_id = uuid4().hex
    now = time.monotonic()
    job = AsyncParseJob(task_id=task_id, created_at=now, updated_at=now)
    _async_jobs[task_id] = job
    asyncio.create_task(_run_async_parse(job, url, file_name, max_chars))
    return json.dumps({"task_id": task_id, "status": "queued"}, ensure_ascii=False)


@mcp.tool()
async def get_file_parse_result(task_id: str) -> str:
    """Get the status/result of a task returned by submit_file_parse."""
    _cleanup_async_jobs()
    job = _async_jobs.get(task_id)
    if not job:
        return json.dumps({"task_id": task_id, "status": "not_found"}, ensure_ascii=False)
    response = {
        "task_id": job.task_id,
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
    if job.status == "success":
        response["result"] = job.result
    elif job.status == "failed":
        response["error"] = job.error
    return json.dumps(response, ensure_ascii=False)


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
