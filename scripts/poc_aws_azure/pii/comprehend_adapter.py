"""AWS Comprehend PII adapter."""

import logging
import math
import time

from botocore.exceptions import ClientError

from scripts.poc_aws_azure.pii.base import (
    PIIAdapter, PIIResult, PIISpan,
    normalize_entity_type, extract_postal_from_address,
)
from scripts.poc_aws_azure.pii.custom_recognizers import enrich_with_custom_entities
from scripts.poc_aws_azure.config import COMPREHEND_COST_PER_UNIT
from scripts.poc_aws_azure.utils.chunker import chunk_text

logger = logging.getLogger("poc")

# Rule 1: Max 100KB (102,400 bytes) per call; use 90K char limit for margin
CHUNK_MAX_CHARS = 90000


class ComprehendAdapter(PIIAdapter):
    def __init__(self, client):
        self.client = client

    def detect(self, text: str, doc_id: str, language: str) -> PIIResult:
        """Run PII detection on text and return the result."""
        start_time = time.time()
        char_count = len(text)

        # Rule 1: Check byte size, chunk if needed
        byte_size = len(text.encode("utf-8"))
        if byte_size > 102400:
            chunks = chunk_text(text, CHUNK_MAX_CHARS)
        else:
            chunks = [{"text": text, "offset": 0}]

        all_spans = []
        total_cost = 0.0

        for chunk in chunks:
            chunk_text_str = chunk["text"]
            chunk_offset = chunk["offset"]

            # Rule 5: Cost calculation
            units = max(3, math.ceil(len(chunk_text_str) / 100))
            chunk_cost = units * COMPREHEND_COST_PER_UNIT
            total_cost += chunk_cost

            # Call API with retry logic
            spans = self._detect_chunk(chunk_text_str, chunk_offset, language, doc_id)
            if spans is None:
                # Error occurred, return error result
                latency = int((time.time() - start_time) * 1000)
                return PIIResult(
                    tool="comprehend", doc_id=doc_id,
                    detected_spans=all_spans,
                    latency_ms=latency, cost_estimate_usd=total_cost,
                    char_count=char_count, error=self._last_error,
                )
            all_spans.extend(spans)

            # Rule 6: 150ms delay between API calls
            time.sleep(0.15)

        # Enrich with custom regex-based SIN and ACCOUNT detection
        all_spans = enrich_with_custom_entities(text, all_spans)

        latency = int((time.time() - start_time) * 1000)
        return PIIResult(
            tool="comprehend",
            doc_id=doc_id,
            detected_spans=all_spans,
            latency_ms=latency,
            cost_estimate_usd=total_cost,
            char_count=char_count,
            error=None,
        )

    def _detect_chunk(self, text: str, offset: int, language: str, doc_id: str) -> list[PIISpan] | None:
        """Detect PII in a single chunk. Returns spans or None on unrecoverable error."""
        self._last_error = None

        # Rule 6, 7: Retry logic with exponential backoff for throttling
        max_retries = 3
        backoff = 1

        for attempt in range(max_retries + 1):
            try:
                # Rule 2: Language code from filename
                response = self.client.detect_pii_entities(
                    Text=text,
                    LanguageCode=language,
                )
                return self._parse_entities(response, offset, text)

            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                error_msg = e.response["Error"]["Message"]

                if error_code == "TextSizeLimitExceededException":
                    # Rule 7: This is a bug in chunking logic
                    byte_size = len(text.encode("utf-8"))
                    logger.error("BUG: TextSizeLimitExceededException for %s, byte size=%d",
                                doc_id, byte_size)
                    self._last_error = f"TextSizeLimitExceededException: byte_size={byte_size}"
                    return None

                elif error_code == "UnsupportedLanguageException":
                    logger.warning("Unsupported language for %s: %s", doc_id, language)
                    self._last_error = f"unsupported_language:{language}"
                    return None

                elif error_code == "ThrottlingException":
                    if attempt < max_retries:
                        logger.warning("Throttled on %s, retry %d/%d (backoff %ds)",
                                      doc_id, attempt + 1, max_retries, backoff)
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                    self._last_error = "ThrottlingException after max retries"
                    return None

                elif error_code == "InternalServerException":
                    if attempt < max_retries:
                        logger.warning("Internal server error on %s, retry %d/%d",
                                      doc_id, attempt + 1, max_retries)
                        time.sleep(5)
                        continue
                    self._last_error = f"InternalServerException: {error_msg}"
                    return None

                else:
                    logger.error("Comprehend error on %s: %s: %s", doc_id, error_code, error_msg)
                    self._last_error = f"{error_code}: {error_msg}"
                    return None

        return None

    def _parse_entities(self, response: dict, offset: int, chunk_text_str: str) -> list[PIISpan]:
        """Rule 3: Parse entities from Comprehend response, adjust offsets, normalize types."""
        spans = []

        for entity in response.get("Entities", []):
            raw_type = entity.get("Type", "")
            # Rule 3: Entity type mapping
            normalized_type = normalize_entity_type(raw_type, "comprehend")

            begin = entity.get("BeginOffset", 0)
            end = entity.get("EndOffset", 0)
            detected_text = chunk_text_str[begin:end]

            # Adjust offsets by chunk offset (Rule 1)
            abs_begin = offset + begin
            abs_end = offset + end

            # Rule 4: No confidence threshold
            confidence = entity.get("Score", 0.0)

            span = PIISpan(
                entity_type=normalized_type,
                text=detected_text,
                start_char=abs_begin,
                end_char=abs_end,
                confidence=confidence,
                original_type=raw_type,
            )
            spans.append(span)

            # ADDRESS_RAW: extract postal code if present
            if normalized_type == "ADDRESS_RAW":
                postal_span = extract_postal_from_address(detected_text, abs_begin)
                if postal_span:
                    spans.append(postal_span)

        return spans
