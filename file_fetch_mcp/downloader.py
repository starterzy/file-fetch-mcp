import mimetypes
from urllib.parse import urljoin, urlparse

import httpx

from .models import DownloadedFile
from .security import validate_url


class DownloadError(RuntimeError):
    pass


class DownloadTooLarge(DownloadError):
    pass


async def download(url: str, *, client: httpx.AsyncClient, max_bytes: int = 50 * 1024 * 1024, max_redirects: int = 3) -> DownloadedFile:
    current = url
    for _ in range(max_redirects + 1):
        validate_url(current)
        async with client.stream("GET", current, follow_redirects=False) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise DownloadError("redirect response has no location")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_bytes:
                raise DownloadTooLarge("download exceeds configured limit")
            chunks = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise DownloadTooLarge("download exceeds configured limit")
                chunks.append(chunk)
            filename = urlparse(current).path.rsplit("/", 1)[-1] or "downloaded-file"
            media_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
            if not media_type:
                media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            return DownloadedFile(data=b"".join(chunks), filename=filename, media_type=media_type, url=current)
    raise DownloadError("too many redirects")
