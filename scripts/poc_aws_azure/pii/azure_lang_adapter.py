"""Azure AI Language PII adapter."""

import logging
import math
import time

from azure.core.exceptions import HttpResponseError

from scripts.poc_aws_azure.pii.base import (
    PIIAdapter, PIIResult, PIISpan,
    normalize_entity_type, extract_postal_from_address,
)
from scripts.poc_aws_azure.pii.custom_recognizers import enrich_with_custom_entities
from scripts.poc_aws_azure.config import AZURE_LANG_COST_PER_1K_RECORDS
from scripts.poc_aws_azure.utils.chunker import chunk_text

logger = logging.getLogger("poc")

# Rule 1: Max 5,120 chars per document; use 5000 for margin
CHUNK_MAX_CHARS = 5000
# Rule 8: Max 10 documents per batch
BATCH_SIZE = 10


class AzureLanguageAdapter(PIIAdapter):
    def __init__(self, client):
        self.client = client

    def detect(self, text: str, doc_id: str, language: str) -> PIIResult:
        """Run PII detection on text and return the result."""
        start_time = time.time()
        char_count = len(text)

        # Rule 1: Chunk if exceeding 5,120 chars
        if len(text) > 5120:
            chunks = chunk_text(text, CHUNK_MAX_CHARS)
        else:
            chunks = [{"text": text, "offset": 0}]

        # Rule 7: Cost calculation
        # 1 record = up to 1000 chars, $1.00 per 1,000 records
        records = max(1, math.ceil(char_count / 1000))
        total_cost = records * (AZURE_LANG_COST_PER_1K_RECORDS / 1000)

        # Rule 8: Group chunks into batches of 10
        all_spans = []
        batch_items = []  # list of (chunk_id, chunk_text, chunk_offset)

        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            batch_items.append((chunk_id, chunk["text"], chunk["offset"]))

        # Process batches
        for batch_start in range(0, len(batch_items), BATCH_SIZE):
            batch = batch_items[batch_start:batch_start + BATCH_SIZE]
            spans, error = self._process_batch(batch, language, doc_id)
            if error:
                latency = int((time.time() - start_time) * 1000)
                return PIIResult(
                    tool="azure_language", doc_id=doc_id,
                    detected_spans=all_spans,
                    latency_ms=latency, cost_estimate_usd=total_cost,
                    char_count=char_count, error=error,
                )
            all_spans.extend(spans)

        # Enrich with custom regex-based SIN and ACCOUNT detection
        all_spans = enrich_with_custom_entities(text, all_spans)

        latency = int((time.time() - start_time) * 1000)
        return PIIResult(
            tool="azure_language",
            doc_id=doc_id,
            detected_spans=all_spans,
            latency_ms=latency,
            cost_estimate_usd=total_cost,
            char_count=char_count,
            error=None,
        )

    def _process_batch(self, batch: list[tuple], language: str, doc_id: str) -> tuple[list[PIISpan], str | None]:
        """Process a batch of up to 10 chunks. Returns (spans, error_or_none)."""
        documents = [{"id": chunk_id, "text": chunk_text} for chunk_id, chunk_text, _ in batch]
        offset_map = {chunk_id: chunk_offset for chunk_id, _, chunk_offset in batch}

        # Rule 11: Retry logic
        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                # Rule 2: Language hint, Rule 3: No categories filter, Rule 4: No domain
                response = self.client.recognize_pii_entities(
                    documents=documents,
                    language=language,
                )
                break
            except HttpResponseError as e:
                if e.status_code == 429:
                    if attempt < max_retries:
                        retry_after = int(e.response.headers.get("Retry-After", 10))
                        logger.warning("Azure Language rate limited on %s, retry after %ds (%d/%d)",
                                      doc_id, retry_after, attempt + 1, max_retries)
                        time.sleep(retry_after)
                        continue
                    return [], f"429: rate limited after {max_retries} retries"
                elif 500 <= e.status_code < 600:
                    if attempt < max_retries:
                        logger.warning("Azure Language server error %d on %s, retry %d/%d",
                                      e.status_code, doc_id, attempt + 1, max_retries)
                        time.sleep(10)
                        continue
                    return [], f"{e.status_code}: {e.message}"
                else:
                    # 4xx: do not retry
                    logger.error("Azure Language error on %s: %d %s",
                                doc_id, e.status_code, e.message)
                    return [], f"{e.status_code}: {e.message}"

        # Rule 9: Parse results — response is a list matching input batch
        spans = []
        for item in response:
            # Rule 9: Check per-document errors
            if item.is_error:
                logger.warning("Azure Language per-doc error on %s: %s - %s",
                              item.id, item.error.code, item.error.message)
                continue

            chunk_offset = offset_map.get(item.id, 0)

            # Rule 5: Parse entities
            for entity in item.entities:
                raw_type = entity.category
                # Some entities have subcategory; use category for mapping
                normalized_type = normalize_entity_type(raw_type, "azure_language")

                # Rule 5: Compute offsets
                abs_start = chunk_offset + entity.offset
                abs_end = abs_start + entity.length

                # Rule 6: No confidence threshold
                span = PIISpan(
                    entity_type=normalized_type,
                    text=entity.text,
                    start_char=abs_start,
                    end_char=abs_end,
                    confidence=entity.confidence_score,
                    original_type=raw_type,
                )
                spans.append(span)

                # ADDRESS_RAW: extract postal code if present
                if normalized_type == "ADDRESS_RAW":
                    postal_span = extract_postal_from_address(entity.text, abs_start)
                    if postal_span:
                        spans.append(postal_span)

        return spans, None
