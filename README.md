# file-fetch-mcp

通过 MCP tool 接收匿名 HTTP/HTTPS 文件下载链接，优先调用独立部署的 MinerU API，失败后使用本地 Python 解析器，并统一返回 Markdown。支持新旧 Office：DOC/DOCX、XLS/XLSX；XML/TXT 直接返回文本内容；ZIP 会遍历其中所有文件并以文件名一级标题拼接各文件内容。其中旧版 DOC 需要配置 antiword、catdoc 或其他受控转换器。WPS/ET/DPS 直接使用本地 WPS 包解析；扫描版 PDF 在本地 fallback 时使用 PyMuPDF + RapidOCR。

同步的 `extract_file_content` 已停用，仅提供 `submit_file_parse` 和 `get_file_parse_result` 异步工具。对于可能超过调用方 300 秒限制的 PDF、ZIP 等文件，先提交任务拿到 `task_id`，再轮询查询结果；后台解析并发上限默认为 5，任务结果默认在进程内保留 1 小时，容器重启后任务状态会丢失。

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

MCP Server 不包含 MinerU 模型和 GPU 运行时；MinerU 应作为独立服务部署。旧版 DOC 解析器通过 `LEGACY_DOC_PARSER` 配置固定可执行文件路径，不能由 URL 或 Agent 传入。扫描版 PDF 在本地 fallback 时会使用 PyMuPDF 渲染页面，再通过 RapidOCR 识别。

PDF OCR 可通过以下环境变量调整：

```text
PDF_OCR_MIN_TEXT_CHARS=20
PDF_OCR_RENDER_SCALE=2
```

### WPS 配置

WPS 文件默认由镜像内置的 `@mdgate/wps` 直接解析为 Markdown，不经过 PDF 和 MinerU。

镜像内置 Node.js 版 `@mdgate/wps` 作为本地 fallback。若要替换它，也可以配置 Python 包适配器，格式为 `模块:函数`。函数接收临时 WPS 文件路径，返回 Markdown 文本或 `ParseResult`：

```text
WPS_LOCAL_PARSER=my_wps_adapter:parse
```

默认镜像已经安装 Node.js 20 和 `@mdgate/wps`，WPS 文件直接使用本地 WPS 解析器转换为 Markdown；PDF、DOCX 等其他文档仍按文件类型路由到 MinerU。
