FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends antiword \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY file_fetch_mcp ./file_fetch_mcp
RUN pip install .

EXPOSE 8080
USER nobody
CMD ["file-fetch-mcp"]
