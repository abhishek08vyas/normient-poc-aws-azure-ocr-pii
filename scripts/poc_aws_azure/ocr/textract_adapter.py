"""AWS Textract OCR adapter."""

import logging
import os
import time
from pathlib import Path

from botocore.exceptions import ClientError

from scripts.poc_aws_azure.ocr.base import (
    OCRAdapter, OCRResult, OCRWord, OCRTable, OCRTableCell, BoundingBox,
)
from scripts.poc_aws_azure.config import TEXTRACT_COST_PER_PAGE
from scripts.poc_aws_azure.utils.serialization import sanitize_response

logger = logging.getLogger("poc")

# Sync API limits
SYNC_MAX_BYTES = 5 * 1024 * 1024  # 5MB
SYNC_SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".pdf"}


class TextractAdapter(OCRAdapter):
    def __init__(self, textract_client, s3_client, bucket_name: str):
        self.textract = textract_client
        self.s3 = s3_client
        self.bucket = bucket_name

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
                tool="textract", file=filename, full_text="",
                words=[], tables=[], page_count=0,
                latency_ms=latency, cost_estimate_usd=0.0,
                raw_response={}, error="unsupported_format",
            )

        file_bytes = path.read_bytes()
        file_size = len(file_bytes)

        # Rule 1: Sync vs async decision
        # Use sync for single-page files <= 5MB (PNGs, single-page PDFs)
        # Use async for multi-page PDFs or large files
        use_sync = (
            file_size <= SYNC_MAX_BYTES
            and ext in SYNC_SUPPORTED_EXTS
            and ext != ".pdf"  # PDFs may be multi-page, use async
        )

        try:
            if use_sync:
                blocks = self._sync_extract(file_bytes)
            else:
                blocks = self._async_extract(path)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_msg = e.response["Error"]["Message"]

            # Rule 11: Error handling
            if error_code == "UnsupportedDocumentException":
                logger.error("OCR textract %s -> ERROR: %s", filename, error_msg)
                latency = int((time.time() - start_time) * 1000)
                return OCRResult(
                    tool="textract", file=filename, full_text="",
                    words=[], tables=[], page_count=0,
                    latency_ms=latency, cost_estimate_usd=0.0,
                    raw_response=sanitize_response(e.response),
                    error=f"{error_code}: {error_msg}",
                )
            elif error_code == "InvalidParameterException":
                logger.error("OCR textract %s -> ERROR: %s", filename, error_msg)
                latency = int((time.time() - start_time) * 1000)
                return OCRResult(
                    tool="textract", file=filename, full_text="",
                    words=[], tables=[], page_count=0,
                    latency_ms=latency, cost_estimate_usd=0.0,
                    raw_response=sanitize_response(e.response),
                    error=f"{error_code}: {error_msg}",
                )
            elif error_code == "ProvisionedThroughputExceededException":
                # Retry up to 3 times with 10s delay
                for retry in range(3):
                    logger.warning("OCR textract %s -> throttled, retry %d/3", filename, retry + 1)
                    time.sleep(10)
                    try:
                        if use_sync:
                            blocks = self._sync_extract(file_bytes)
                        else:
                            blocks = self._async_extract(path)
                        break
                    except ClientError as retry_e:
                        if retry == 2:
                            latency = int((time.time() - start_time) * 1000)
                            return OCRResult(
                                tool="textract", file=filename, full_text="",
                                words=[], tables=[], page_count=0,
                                latency_ms=latency, cost_estimate_usd=0.0,
                                raw_response=sanitize_response(retry_e.response),
                                error=f"ProvisionedThroughputExceededException after 3 retries",
                            )
            else:
                logger.error("OCR textract %s -> ERROR: %s: %s", filename, error_code, error_msg)
                latency = int((time.time() - start_time) * 1000)
                return OCRResult(
                    tool="textract", file=filename, full_text="",
                    words=[], tables=[], page_count=0,
                    latency_ms=latency, cost_estimate_usd=0.0,
                    raw_response=sanitize_response(e.response),
                    error=f"{error_code}: {error_msg}",
                )

        latency = int((time.time() - start_time) * 1000)

        # Parse blocks
        full_text = self._assemble_text(blocks)
        words = self._extract_words(blocks)
        tables = self._extract_tables(blocks)
        page_count = max((b.get("Page", 1) for b in blocks), default=1)

        # Rule 6: Cost calculation
        cost = page_count * TEXTRACT_COST_PER_PAGE

        logger.info("OCR textract %s -> %d pages, %dms, $%.4f",
                     filename, page_count, latency, cost)

        return OCRResult(
            tool="textract",
            file=filename,
            full_text=full_text,
            words=words,
            tables=tables,
            page_count=page_count,
            latency_ms=latency,
            cost_estimate_usd=cost,
            raw_response={},  # raw response stored separately to avoid huge dataclass
            error=None,
        )

    def _sync_extract(self, file_bytes: bytes) -> list[dict]:
        """Rule 1: Synchronous API for small single-page files."""
        response = self.textract.analyze_document(
            Document={"Bytes": file_bytes},
            FeatureTypes=["TABLES", "FORMS"],  # Rule 4
        )
        return response.get("Blocks", [])

    def _async_extract(self, file_path: Path) -> list[dict]:
        """Rule 1, 3, 5: Async API with S3 upload, polling, pagination."""
        filename = file_path.name
        s3_key = f"poc-input/{filename}"

        # Rule 3: Upload to S3
        self.s3.upload_file(str(file_path), self.bucket, s3_key)
        logger.debug("Uploaded %s to s3://%s/%s", filename, self.bucket, s3_key)

        try:
            # Start async job
            response = self.textract.start_document_analysis(
                DocumentLocation={
                    "S3Object": {
                        "Bucket": self.bucket,
                        "Name": s3_key,
                    }
                },
                FeatureTypes=["TABLES", "FORMS"],  # Rule 4
            )
            job_id = response["JobId"]
            logger.debug("Started Textract job %s for %s", job_id, filename)

            # Rule 2: Poll with exponential backoff
            blocks = self._poll_job(job_id, filename)
        finally:
            # Rule 3: Delete S3 object after processing
            try:
                self.s3.delete_object(Bucket=self.bucket, Key=s3_key)
                # Verify deletion
                try:
                    self.s3.head_object(Bucket=self.bucket, Key=s3_key)
                    logger.warning("S3 object still exists after deletion: %s", s3_key)
                except ClientError as e:
                    if e.response["Error"]["Code"] == "404":
                        logger.debug("Verified deletion of s3://%s/%s", self.bucket, s3_key)
                    else:
                        logger.warning("Could not verify S3 deletion: %s", e)
            except ClientError as e:
                logger.warning("Failed to delete S3 object %s: %s", s3_key, e)

        return blocks

    def _poll_job(self, job_id: str, filename: str) -> list[dict]:
        """Rule 2: Poll with exponential backoff. Rule 5: Paginate."""
        wait = 5
        max_wait = 30
        max_retries = 10

        for attempt in range(max_retries):
            time.sleep(wait)
            response = self.textract.get_document_analysis(JobId=job_id)
            status = response["JobStatus"]

            if status == "SUCCEEDED":
                # Rule 5: Collect all blocks across pages
                blocks = response.get("Blocks", [])
                while "NextToken" in response:
                    response = self.textract.get_document_analysis(
                        JobId=job_id, NextToken=response["NextToken"]
                    )
                    blocks.extend(response.get("Blocks", []))
                logger.debug("Textract job %s completed: %d blocks", job_id, len(blocks))
                return blocks
            elif status == "FAILED":
                error_msg = response.get("StatusMessage", "Unknown error")
                raise ClientError(
                    {"Error": {"Code": "JobFailed", "Message": error_msg}},
                    "GetDocumentAnalysis",
                )
            else:
                logger.debug("Textract job %s status: %s (attempt %d/%d)",
                            job_id, status, attempt + 1, max_retries)
                wait = min(wait * 2, max_wait)

        raise ClientError(
            {"Error": {"Code": "JobTimeout", "Message": f"Job {job_id} did not complete after {max_retries} polls"}},
            "GetDocumentAnalysis",
        )

    def _assemble_text(self, blocks: list[dict]) -> str:
        """Rule 8: Full text from LINE blocks, ordered by page then position."""
        lines = []
        for b in blocks:
            if b.get("BlockType") == "LINE":
                page = b.get("Page", 1)
                top = b.get("Geometry", {}).get("BoundingBox", {}).get("Top", 0)
                lines.append((page, top, b.get("Text", "")))
        lines.sort(key=lambda x: (x[0], x[1]))
        return "\n".join(text for _, _, text in lines)

    def _extract_words(self, blocks: list[dict]) -> list[OCRWord]:
        """Rule 9: Extract words with confidence normalization (0-100 -> 0-1)."""
        words = []
        for b in blocks:
            if b.get("BlockType") == "WORD":
                bbox_data = b.get("Geometry", {}).get("BoundingBox", {})
                bbox = BoundingBox(
                    left=bbox_data.get("Left", 0),
                    top=bbox_data.get("Top", 0),
                    width=bbox_data.get("Width", 0),
                    height=bbox_data.get("Height", 0),
                )
                words.append(OCRWord(
                    text=b.get("Text", ""),
                    confidence=b.get("Confidence", 0) / 100.0,  # Rule 9: normalize
                    bbox=bbox,
                    page=b.get("Page", 1),
                ))
        return words

    def _extract_tables(self, blocks: list[dict]) -> list[OCRTable]:
        """Rule 10: Extract tables via block relationships."""
        # Build block index by ID
        block_by_id = {b["Id"]: b for b in blocks if "Id" in b}

        tables = []
        for b in blocks:
            if b.get("BlockType") != "TABLE":
                continue

            # Find child CELL blocks
            child_ids = []
            for rel in b.get("Relationships", []):
                if rel.get("Type") == "CHILD":
                    child_ids.extend(rel.get("Ids", []))

            cells = []
            max_row = 0
            max_col = 0
            for cell_id in child_ids:
                cell_block = block_by_id.get(cell_id)
                if not cell_block or cell_block.get("BlockType") != "CELL":
                    continue

                # Rule 10: 1-indexed -> 0-indexed
                row_idx = cell_block.get("RowIndex", 1) - 1
                col_idx = cell_block.get("ColumnIndex", 1) - 1
                row_span = cell_block.get("RowSpan", 1)
                col_span = cell_block.get("ColumnSpan", 1)

                max_row = max(max_row, row_idx + row_span)
                max_col = max(max_col, col_idx + col_span)

                # Get cell text from child WORD blocks
                cell_text_parts = []
                for cell_rel in cell_block.get("Relationships", []):
                    if cell_rel.get("Type") == "CHILD":
                        for word_id in cell_rel.get("Ids", []):
                            word_block = block_by_id.get(word_id)
                            if word_block and word_block.get("BlockType") == "WORD":
                                cell_text_parts.append(word_block.get("Text", ""))

                cell_text = " ".join(cell_text_parts)
                confidence = cell_block.get("Confidence", 0) / 100.0

                cells.append(OCRTableCell(
                    text=cell_text,
                    row_index=row_idx,
                    col_index=col_idx,
                    row_span=row_span,
                    col_span=col_span,
                    confidence=confidence,
                ))

            tables.append(OCRTable(
                cells=cells,
                row_count=max_row,
                col_count=max_col,
                page=b.get("Page", 1),
            ))

        return tables
