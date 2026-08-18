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

默认配置通过环境变量注入：`MINERU_API_BASE_URL=http://mineru-api:8000`、`MINERU_TASK_TIMEOUT_SECONDS=180`、`MINERU_POLL_INTERVAL_SECONDS=2`、`MINERU_BACKEND=pipeline`、`MINERU_VLM_URL=`、`DOWNLOAD_MAX_BYTES=52428800`。

MinerU 请求默认使用 `pipeline` 后端，适合 CPU 部署；MCP 会将 `MINERU_BACKEND` 传给 MinerU 的 `backend` 字段。只有 `MINERU_VLM_URL` 非空时，才会额外传递 MinerU API 的 `url` 字段，用于 VLM HTTP Client 等需要远端 OpenAI 兼容服务的后端。

出于 SSRF 防护，默认拒绝 `localhost`、私网 IP 以及解析到私网/本地地址的域名。若 MCP 仅部署在可信内网并且确实需要抓取内网文件，可设置 `ALLOW_PRIVATE_NETWORK_URLS=true`（Docker Compose 中也可覆盖该变量）。开启后请确保 MCP 接口本身仅对可信调用方开放，因为 URL 参数将可以访问该运行环境可达的私有网络地址。

MCP Server 不包含 MinerU 模型和 GPU 运行时；MinerU 应作为独立服务部署。旧版 DOC 解析器通过 `LEGACY_DOC_PARSER` 配置固定可执行文件路径，不能由 URL 或 Agent 传入。
