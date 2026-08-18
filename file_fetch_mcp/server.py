import os

from mcp.server.fastmcp import FastMCP

from .service import FileFetchService

mcp = FastMCP(
    "file-fetch-mcp",
    host=os.getenv("MCP_HTTP_HOST", "127.0.0.1"),
    port=int(os.getenv("MCP_HTTP_PORT", "8000")),
    streamable_http_path="/mcp",
)
service = FileFetchService(max_bytes=int(os.getenv("DOWNLOAD_MAX_BYTES", str(50 * 1024 * 1024))))


@mcp.tool()
async def extract_file_content(url: str, file_name: str | None = None, max_chars: int = 50_000) -> str:
    """Download an anonymous HTTP/HTTPS file URL and return MinerU-style Markdown content."""
    result = await service.extract(url, file_name=file_name, max_chars=max_chars)
    if result.warnings:
        return result.markdown + "\n\n" + "\n".join(f"> Warning: {warning}" for warning in result.warnings)
    return result.markdown


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
