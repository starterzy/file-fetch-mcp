"""Adapters for Kingsoft WPS conversion and local-package fallback parsing."""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .models import ParseResult

WPS_SUFFIXES = {".wps", ".et", ".dps"}


class WPSParserError(RuntimeError):
    pass


def is_wps_filename(filename: str) -> bool:
    return Path(filename).suffix.lower() in WPS_SUFFIXES


def parse_with_local_package(path: Path) -> ParseResult:
    """Call the configured local WPS package adapter.

    ``WPS_LOCAL_PARSER`` must be ``package.module:function``.  The function
    receives the temporary file path and may return ``ParseResult`` or text.
    """
    spec = os.getenv("WPS_LOCAL_PARSER", "").strip()
    if not spec:
        return _parse_with_node_package(path)
    if ":" not in spec:
        raise WPSParserError("WPS_LOCAL_PARSER must use module:function")
    module_name, function_name = spec.rsplit(":", 1)
    try:
        function = getattr(importlib.import_module(module_name), function_name)
    except (ImportError, AttributeError) as exc:
        raise WPSParserError(f"cannot load WPS local parser {spec}: {exc}") from exc
    result: Any = function(str(path))
    if isinstance(result, ParseResult):
        return result
    if isinstance(result, bytes):
        result = result.decode("utf-8", errors="replace")
    if isinstance(result, str) and result.strip():
        return ParseResult(markdown="# WPS Document\n\n" + result.strip(), format="wps", parser="wps-local")
    raise WPSParserError("WPS local parser returned no text")


def _parse_with_node_package(path: Path) -> ParseResult:
    script = Path(os.getenv("WPS_NODE_PARSER_SCRIPT", "/opt/wps-parser/index.mjs"))
    node = shutil.which(os.getenv("WPS_NODE_BIN", "node"))
    if not node or not script.is_file():
        raise WPSParserError(
            "Kingsoft WPS parser is not installed; expected Node.js and "
            f"{script} or set WPS_LOCAL_PARSER=module:function"
        )
    completed = subprocess.run(
        [node, str(script), str(path)],
        check=False,
        capture_output=True,
        timeout=float(os.getenv("WPS_LOCAL_PARSER_TIMEOUT_SECONDS", "60")),
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise WPSParserError(detail or "Kingsoft WPS parser failed")
    markdown = completed.stdout.decode("utf-8", errors="replace").strip()
    if not markdown:
        raise WPSParserError("Kingsoft WPS parser returned no Markdown")
    return ParseResult(markdown=markdown, format="wps", parser="wps-local")
