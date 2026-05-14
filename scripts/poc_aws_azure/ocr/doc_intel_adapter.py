"""Azure AI Document Intelligence OCR adapter."""

import logging
import time
from pathlib import Path

from azure.core.exceptions import HttpResponseError

from scripts.poc_aws_azure.ocr.base import (
    OCRAdapter, OCRResult, OCRWord, OCRTable, OCRTableCell, BoundingBox,
)
from scripts.poc_aws_azure.config import DOC_INTEL_COST_PER_PAGE, CONTENT_TYPE_MAP
from scripts.poc_aws_azure.utils.serialization import to_serializable, sanitize_response

logger = logging.getLogger("poc")


class DocIntelAdapter(OCRAdapter):
    def __init__(self, client):
        self.client = client

    def extract(self, file_path: str) -> OCRResult:
        """Run OCR on a single file and return the result."""
        path = Path(file_path)
        filename = path.name
        ext = path.suffix.lower()
        start_time = time.time()

        # Rule 12: Excel files unsupported
        if ext in (".xlsx", ".xls"):
            latency = int((time.time() - start_time) * 1000)
            return OCRResult(
                tool="azure_doc_intel", file=filename, full_text="",
                words=[], tables=[], page_count=0,
                latency_ms=latency, cost_estimate_usd=0.0,
                raw_response={}, error="unsupported_format",
            )

        # Rule 2: Detect content type from extension
        content_type = CONTENT_TYPE_MAP.get(ext)
        if not content_type:
            latency = int((time.time() - start_time) * 1000)
            return OCRResult(
                tool="azure_doc_intel", file=filename, full_text="",
                words=[], tables=[], page_count=0,
                latency_ms=latency, cost_estimate_usd=0.0,
                raw_response={}, error=f"unsupported_content_type: {ext}",
            )

        file_bytes = path.read_bytes()

        # Rule 11: Error handling with retries
        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                # Rule 1, 2: Use prebuilt-layout with file bytes
                import base64
                from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
                request = AnalyzeDocumentRequest(
                    bytes_source=base64.b64encode(file_bytes).decode("ascii"),
                )
                poller = self.client.begin_analyze_document(
                    "prebuilt-layout",
                    body=request,
                )
                # Rule 3: Poll with timeout
                result = poller.result(timeout=300)
                break
            except TimeoutError:
                latency = int((time.time() - start_time) * 1000)
                logger.error("OCR azure_doc_intel %s -> ERROR: timeout", filename)
                return OCRResult(
                    tool="azure_doc_intel", file=filename, full_text="",
                    words=[], tables=[], page_count=0,
                    latency_ms=latency, cost_estimate_usd=0.0,
                    raw_response={}, error="timeout",
                )
            except HttpResponseError as e:
                if e.status_code == 400:
                    # Bad request — do not retry
                    latency = int((time.time() - start_time) * 1000)
                    logger.error("OCR azure_doc_intel %s -> ERROR: %s", filename, e.message)
                    return OCRResult(
                        tool="azure_doc_intel", file=filename, full_text="",
                        words=[], tables=[], page_count=0,
                        latency_ms=latency, cost_estimate_usd=0.0,
                        raw_response={}, error=f"400: {e.message}",
                    )
                elif e.status_code == 429:
                    # Rate limit — retry with Retry-After
                    if attempt < max_retries:
                        retry_after = int(e.response.headers.get("Retry-After", 10))
                        logger.warning("OCR azure_doc_intel %s -> rate limited, retry after %ds (attempt %d/%d)",
                                      filename, retry_after, attempt + 1, max_retries)
                        time.sleep(retry_after)
                        continue
                    latency = int((time.time() - start_time) * 1000)
                    return OCRResult(
                        tool="azure_doc_intel", file=filename, full_text="",
                        words=[], tables=[], page_count=0,
                        latency_ms=latency, cost_estimate_usd=0.0,
                        raw_response={}, error=f"429: rate limited after {max_retries} retries",
                    )
                elif 500 <= e.status_code < 600:
                    # Server error — retry with 10s delay
                    if attempt < max_retries:
                        logger.warning("OCR azure_doc_intel %s -> server error %d, retry %d/%d",
                                      filename, e.status_code, attempt + 1, max_retries)
                        time.sleep(10)
                        continue
                    latency = int((time.time() - start_time) * 1000)
                    return OCRResult(
                        tool="azure_doc_intel", file=filename, full_text="",
                        words=[], tables=[], page_count=0,
                        latency_ms=latency, cost_estimate_usd=0.0,
                        raw_response={}, error=f"{e.status_code}: {e.message}",
                    )
                else:
                    # Other error — do not retry
                    latency = int((time.time() - start_time) * 1000)
                    logger.error("OCR azure_doc_intel %s -> ERROR: %d %s",
                                filename, e.status_code, e.message)
                    return OCRResult(
                        tool="azure_doc_intel", file=filename, full_text="",
                        words=[], tables=[], page_count=0,
                        latency_ms=latency, cost_estimate_usd=0.0,
                        raw_response={}, error=f"{e.status_code}: {e.message}",
                    )

        latency = int((time.time() - start_time) * 1000)

        # Rule 7: Full text assembly
        full_text = result.content or ""

        # Rule 10: Page count
        page_count = len(result.pages) if result.pages else 0

        # Rule 8: Word extraction
        words = self._extract_words(result)

        # Rule 9: Table extraction
        tables = self._extract_tables(result)

        # Rule 5: Cost calculation
        cost = page_count * DOC_INTEL_COST_PER_PAGE

        logger.info("OCR azure_doc_intel %s -> %d pages, %dms, $%.4f",
                     filename, page_count, latency, cost)

        return OCRResult(
            tool="azure_doc_intel",
            file=filename,
            full_text=full_text,
            words=words,
            tables=tables,
            page_count=page_count,
            latency_ms=latency,
            cost_estimate_usd=cost,
            raw_response={},
            error=None,
        )

    def _polygon_to_bbox(self, polygon) -> BoundingBox:
        """Rule 6: Convert polygon [x1,y1,...,x4,y4] to BoundingBox."""
        if not polygon or len(polygon) < 8:
            return BoundingBox(left=0, top=0, width=0, height=0)
        xs = polygon[0::2]
        ys = polygon[1::2]
        left = min(xs)
        top = min(ys)
        width = max(xs) - left
        height = max(ys) - top
        return BoundingBox(left=left, top=top, width=width, height=height)

    def _extract_words(self, result) -> list[OCRWord]:
        """Rule 8: Extract words from all pages."""
        words = []
        if not result.pages:
            return words
        for page in result.pages:
            page_num = page.page_number
            if not page.words:
                continue
            for word in page.words:
                polygon = word.polygon if hasattr(word, "polygon") and word.polygon else []
                bbox = self._polygon_to_bbox(polygon)
                confidence = word.confidence if word.confidence is not None else 0.0
                words.append(OCRWord(
                    text=word.content,
                    confidence=confidence,
                    bbox=bbox,
                    page=page_num,
                ))
        return words

    def _extract_tables(self, result) -> list[OCRTable]:
        """Rule 9: Extract tables with cells."""
        tables = []
        if not result.tables:
            return tables
        for table in result.tables:
            cells = []
            if table.cells:
                for cell in table.cells:
                    # Cell confidence: use 1.0 if not available at cell level
                    confidence = 1.0
                    if hasattr(cell, "confidence") and cell.confidence is not None:
                        confidence = cell.confidence

                    cells.append(OCRTableCell(
                        text=cell.content or "",
                        row_index=cell.row_index,
                        col_index=cell.column_index,
                        row_span=cell.row_span if cell.row_span else 1,
                        col_span=cell.column_span if cell.column_span else 1,
                        confidence=confidence,
                    ))

            # Determine page from bounding regions if available
            page = 1
            if hasattr(table, "bounding_regions") and table.bounding_regions:
                page = table.bounding_regions[0].page_number

            tables.append(OCRTable(
                cells=cells,
                row_count=table.row_count,
                col_count=table.column_count,
                page=page,
            ))
        return tables
