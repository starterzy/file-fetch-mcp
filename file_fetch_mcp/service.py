import os
import io
import mimetypes
from pathlib import Path
from zipfile import ZipFile

import httpx

from .downloader import download
from .mineru_client import MinerUClient
from .models import ExtractResult, ParseResult
from .parsers import UnsupportedFormat, parse_local_bytes
from .wps import is_wps_filename


class FileFetchService:
    def __init__(self, *, http: httpx.AsyncClient | None = None, mineru=None, max_bytes: int = 50 * 1024 * 1024, max_chars: int = 200_000, allow_private_urls: bool = False):
        self.http = http
        self.max_bytes = max_bytes
        self.max_chars = max_chars
        self.allow_private_urls = allow_private_urls
        self.mineru = mineru or MinerUClient(
            os.getenv("MINERU_API_BASE_URL", "http://mineru-api:8000"),
            task_timeout=float(os.getenv("MINERU_TASK_TIMEOUT_SECONDS", "180")),
            poll_interval=float(os.getenv("MINERU_POLL_INTERVAL_SECONDS", "2")),
            backend=os.getenv("MINERU_BACKEND", "pipeline"),
            vlm_url=os.getenv("MINERU_VLM_URL", ""),
        )

    async def extract(self, url: str, *, file_name: str | None = None, max_chars: int | None = None) -> ExtractResult:
        own_client = self.http is None
        client = self.http or httpx.AsyncClient(timeout=httpx.Timeout(30, read=120))
        try:
            downloaded = await download(url, client=client, max_bytes=self.max_bytes, allow_private=self.allow_private_urls)
            filename = file_name or downloaded.filename
            markdown, file_format, parser, warnings = await self._route_bytes(
                downloaded.data, filename, downloaded.media_type
            )
            limit = max_chars or self.max_chars
            truncated = len(markdown) > limit
            if truncated:
                markdown = markdown[:limit]
                warnings.append("result truncated to max_chars")
            return ExtractResult(markdown, filename, downloaded.media_type, file_format, parser, len(downloaded.data), warnings, truncated)
        finally:
            if own_client:
                await client.aclose()

    async def _route_bytes(self, data: bytes, filename: str, media_type: str | None):
        """Apply the same type routing to a top-level file and ZIP entries."""
        if Path(filename).suffix.lower() == ".zip":
            return await self._route_zip(data)

        warnings: list[str] = []
        if is_wps_filename(filename):
            local = parse_local_bytes(data, filename, media_type)
            warnings.extend(local.warnings)
            return local.markdown, local.format, "wps-local", warnings

        if Path(filename).suffix.lower() in {".xml", ".txt"}:
            local = parse_local_bytes(data, filename, media_type)
            return local.markdown, local.format, "local", local.warnings.copy()

        try:
            parsed = await self.mineru.parse(data, filename, media_type)
            return parsed.markdown, Path(filename).suffix.lower().lstrip(".") or "unknown", "mineru", warnings
        except Exception as exc:
            local = parse_local_bytes(data, filename, media_type)
            warnings.append(f"MinerU fallback: {type(exc).__name__}")
            warnings.extend(local.warnings)
            return local.markdown, local.format, "local", warnings

    async def _route_zip(self, data: bytes):
        """Route each ZIP entry independently so document entries can use MinerU."""
        blocks: list[str] = []
        file_names: list[str] = []
        warnings: list[str] = []
        parsers: set[str] = set()
        max_files = int(os.getenv("ZIP_MAX_FILES", "1000"))
        max_uncompressed_bytes = int(os.getenv("ZIP_MAX_UNCOMPRESSED_BYTES", str(200 * 1024 * 1024)))
        max_compression_ratio = float(os.getenv("ZIP_MAX_COMPRESSION_RATIO", "1000"))
        total_uncompressed_bytes = 0

        with ZipFile(io.BytesIO(data)) as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                if len(file_names) >= max_files:
                    raise UnsupportedFormat("ZIP contains too many files")
                total_uncompressed_bytes += entry.file_size
                if total_uncompressed_bytes > max_uncompressed_bytes:
                    raise UnsupportedFormat("ZIP uncompressed content exceeds configured limit")
                if entry.compress_size and entry.file_size / entry.compress_size > max_compression_ratio:
                    raise UnsupportedFormat("ZIP compression ratio exceeds configured limit")
                file_names.append(entry.filename)
                entry_media_type = mimetypes.guess_type(entry.filename)[0] or "application/octet-stream"
                markdown, _file_format, parser, entry_warnings = await self._route_bytes(
                    archive.read(entry), entry.filename, entry_media_type
                )
                blocks.append(f"# {entry.filename}\n\n{markdown}")
                parsers.add(parser)
                warnings.extend(f"{entry.filename}: {warning}" for warning in entry_warnings)

        if parsers == {"local"} or not parsers:
            parser = "local"
        elif parsers == {"mineru"}:
            parser = "zip+mineru"
        else:
            parser = "zip+mixed"
        return "\n\n".join(blocks), "zip", parser, warnings
