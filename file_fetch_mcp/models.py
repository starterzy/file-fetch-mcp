from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class DownloadedFile:
    data: bytes
    filename: str
    media_type: str
    url: str


@dataclass(slots=True)
class ParseResult:
    markdown: str
    format: str
    parser: str = "local"
    metadata: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExtractResult:
    markdown: str
    filename: str
    media_type: str
    format: str
    parser: str
    size_bytes: int
    warnings: list[str] = field(default_factory=list)
    truncated: bool = False

    def as_dict(self) -> dict:
        return {
            "source": {
                "file_name": self.filename,
                "media_type": self.media_type,
                "size_bytes": self.size_bytes,
            },
            "extraction": {
                "format": self.format,
                "parser": self.parser,
                "truncated": self.truncated,
                "warnings": self.warnings,
            },
            "markdown": self.markdown,
        }
