"""OCR data contracts and abstract adapter base."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class BoundingBox:
    left: float    # 0.0-1.0 normalized
    top: float     # 0.0-1.0 normalized
    width: float   # 0.0-1.0 normalized
    height: float  # 0.0-1.0 normalized


@dataclass
class OCRWord:
    text: str
    confidence: float          # 0.0-1.0
    bbox: BoundingBox
    page: int                  # 1-indexed


@dataclass
class OCRTableCell:
    text: str
    row_index: int             # 0-indexed
    col_index: int             # 0-indexed
    row_span: int              # default 1
    col_span: int              # default 1
    confidence: float


@dataclass
class OCRTable:
    cells: list[OCRTableCell]
    row_count: int
    col_count: int
    page: int


@dataclass
class OCRResult:
    tool: str                  # "textract" | "azure_doc_intel"
    file: str                  # filename
    full_text: str             # concatenated extracted text
    words: list[OCRWord]
    tables: list[OCRTable]
    page_count: int
    latency_ms: int            # wall-clock milliseconds
    cost_estimate_usd: float   # estimated cost for this single call
    raw_response: dict         # sanitized API response
    error: str | None          # null on success; error message on failure


class OCRAdapter(ABC):
    @abstractmethod
    def extract(self, file_path: str) -> OCRResult:
        """Run OCR on a single file and return the result."""
        ...
