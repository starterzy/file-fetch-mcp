import asyncio
import io
import zipfile
from dataclasses import dataclass

import httpx


class MinerUError(RuntimeError):
    pass


@dataclass(slots=True)
class MinerUResult:
    markdown: str
    parser: str = "mineru"
    metadata: dict | None = None


class MinerUClient:
    def __init__(
        self,
        base_url: str,
        *,
        http: httpx.AsyncClient | None = None,
        task_timeout: float = 180,
        poll_interval: float = 2,
        backend: str = "pipeline",
        vlm_url: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.http = http
        self.task_timeout = task_timeout
        self.poll_interval = poll_interval
        self.backend = backend.strip() or "pipeline"
        self.vlm_url = vlm_url.strip()

    async def parse(self, data: bytes, filename: str, media_type: str) -> MinerUResult:
        if self.http is None:
            async with httpx.AsyncClient(timeout=30) as client:
                return await self._parse(client, data, filename, media_type)
        return await self._parse(self.http, data, filename, media_type)

    async def _parse(self, client: httpx.AsyncClient, data: bytes, filename: str, media_type: str) -> MinerUResult:
        try:
            request_data = {
                "return_md": "true",
                "response_format_zip": "false",
                "backend": self.backend,
            }
            if self.vlm_url:
                request_data["url"] = self.vlm_url
            response = await client.post(
                f"{self.base_url}/file_parse",
                files={"files": (filename, io.BytesIO(data), media_type)},
                data=request_data,
            )
            response.raise_for_status()
            if "application/json" not in response.headers.get("content-type", ""):
                return self._result_from_bytes(response.content)
            payload = response.json()
            task_id = payload.get("task_id") or payload.get("data", {}).get("task_id")
            if not task_id:
                return self._result_from_payload(payload)
            deadline = asyncio.get_running_loop().time() + self.task_timeout
            while True:
                status_response = await client.get(f"{self.base_url}/tasks/{task_id}")
                status_response.raise_for_status()
                status = status_response.json()
                state = str(status.get("state") or status.get("status") or "").lower()
                if state in {"failed", "error", "cancelled", "canceled"}:
                    raise MinerUError(status.get("error") or status.get("message") or "MinerU task failed")
                if state in {"done", "success", "completed", "succeeded"}:
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    raise MinerUError("MinerU task timed out")
                await asyncio.sleep(self.poll_interval)
            result_response = await client.get(f"{self.base_url}/tasks/{task_id}/result")
            result_response.raise_for_status()
            if "application/json" not in result_response.headers.get("content-type", ""):
                return self._result_from_bytes(result_response.content)
            return self._result_from_payload(result_response.json())
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise MinerUError(f"MinerU API request failed: {exc}") from exc

    @staticmethod
    def _result_from_payload(payload: dict) -> MinerUResult:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        markdown = payload.get("markdown") or payload.get("md_content") or data.get("markdown") or data.get("md_content") or payload.get("content")
        if not markdown and isinstance(payload.get("results"), dict):
            for result in payload["results"].values():
                if isinstance(result, dict):
                    markdown = result.get("markdown") or result.get("md_content") or result.get("content")
                    if markdown:
                        break
        if not isinstance(markdown, str) or not markdown.strip():
            raise MinerUError("MinerU returned no Markdown")
        return MinerUResult(markdown=markdown, metadata=payload.get("metadata"))

    @staticmethod
    def _result_from_bytes(data: bytes) -> MinerUResult:
        if data.startswith(b"PK"):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                markdown_files = [name for name in archive.namelist() if name.lower().endswith(".md")]
                if not markdown_files:
                    raise MinerUError("MinerU result archive contains no Markdown")
                markdown = archive.read(markdown_files[0]).decode("utf-8", errors="replace")
        else:
            markdown = data.decode("utf-8", errors="replace")
        if not markdown.strip():
            raise MinerUError("MinerU returned empty Markdown")
        return MinerUResult(markdown=markdown)
