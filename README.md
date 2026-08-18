# file-fetch-mcp

通过 MCP tool 接收匿名 HTTP/HTTPS 文件下载链接，优先调用独立部署的 MinerU API，失败后使用本地 Python 解析器，并统一返回 Markdown。支持新旧 Office：DOC/DOCX、XLS/XLSX；其中旧版 DOC 需要配置 antiword、catdoc 或其他受控转换器。

## 开发

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version   # 应为 3.11 或 3.12

pip install -e ".[dev,ocr]"
pytest
```

## 运行

本地 stdio：

```powershell
file-fetch-mcp
```

容器化 Streamable HTTP：

```powershell
docker compose up --build
```

默认配置通过环境变量注入：`MINERU_API_BASE_URL=http://mineru-api:8000`、`MINERU_TASK_TIMEOUT_SECONDS=180`、`DOWNLOAD_MAX_BYTES=52428800`。

MCP Server 不包含 MinerU 模型和 GPU 运行时；MinerU 应作为独立服务部署。旧版 DOC 解析器通过 `LEGACY_DOC_PARSER` 配置固定可执行文件路径，不能由 URL 或 Agent 传入。
