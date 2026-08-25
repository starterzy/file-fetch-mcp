FROM node:20-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv antiword \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libxcb1 \
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
RUN pip install --no-cache-dir ".[ocr]"

ENV WPS_NODE_PARSER_SCRIPT=/opt/wps-parser/index.mjs \
    HOME=/tmp

EXPOSE 8080
USER nobody
CMD ["file-fetch-mcp"]
