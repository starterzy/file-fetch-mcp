import os
from pathlib import Path

import httpx

from .downloader import download
from .mineru_client import MinerUClient
from .models import ExtractResult, ParseResult
from .parsers import parse_local_bytes


class FileFetchService:
    def __init__(self, *, http: httpx.AsyncClient | None = None, mineru=None, max_bytes: int = 50 * 1024 * 1024, max_chars: int = 200_000):
        self.http = http
        self.max_bytes = max_bytes
        self.max_chars = max_chars
        self.mineru = mineru or MinerUClient(
            os.getenv("MINERU_API_BASE_URL", "http://mineru-api:8000"),
            task_timeout=float(os.getenv("MINERU_TASK_TIMEOUT_SECONDS", "180")),
            poll_interval=float(os.getenv("MINERU_POLL_INTERVAL_SECONDS", "2")),
        )

    async def extract(self, url: str, *, file_name: str | None = None, max_chars: int | None = None) -> ExtractResult:
        own_client = self.http is None
        client = self.http or httpx.AsyncClient(timeout=httpx.Timeout(30, read=120))
        try:
            downloaded = await download(url, client=client, max_bytes=self.max_bytes)
            filename = file_name or downloaded.filename
            warnings: list[str] = []
            try:
                parsed = await self.mineru.parse(downloaded.data, filename, downloaded.media_type)
                markdown = parsed.markdown
                parser = "mineru"
                file_format = Path(filename).suffix.lower().lstrip(".") or "unknown"
            except Exception as exc:
                local = parse_local_bytes(downloaded.data, filename, downloaded.media_type)
                markdown = local.markdown
                parser = "local"
                file_format = local.format
                warnings.append(f"MinerU fallback: {type(exc).__name__}")
                warnings.extend(local.warnings)
            limit = max_chars or self.max_chars
            truncated = len(markdown) > limit
            if truncated:
                markdown = markdown[:limit]
                warnings.append("result truncated to max_chars")
            return ExtractResult(markdown, filename, downloaded.media_type, file_format, parser, len(downloaded.data), warnings, truncated)
        finally:
            if own_client:
                await client.aclose()
