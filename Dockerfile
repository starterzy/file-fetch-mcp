FROM node:20-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv antiword libreoffice-writer \
    && python3 -m venv /opt/venv \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /opt/wps-parser
COPY wps-parser/package.json wps-parser/package-lock.json ./
RUN npm ci --omit=dev
COPY wps-parser/index.mjs ./

WORKDIR /app
COPY pyproject.toml README.md ./
COPY file_fetch_mcp ./file_fetch_mcp
RUN pip install --no-cache-dir .

ENV WPS_NODE_PARSER_SCRIPT=/opt/wps-parser/index.mjs \
    WPS_TO_PDF_COMMAND="soffice --headless --convert-to pdf --outdir {output_dir} {input}" \
    HOME=/tmp

EXPOSE 8080
USER nobody
CMD ["file-fetch-mcp"]
