"""Custom regex-based recognizers for Canadian SIN and account numbers.

Neither AWS Comprehend nor Azure Language detects Canadian SIN natively.
These recognizers run as a post-processing enrichment on the input text,
adding SIN and ACCOUNT spans that the managed services miss.
"""

import re
from scripts.poc_aws_azure.pii.base import PIISpan
from scripts.poc_aws_azure.corpus.sin_utils import validate_sin


# SIN patterns: 9 contiguous digits, or 3-3-3 with spaces/dashes
SIN_PATTERNS = [
    re.compile(r"(?<!\d)\d{3}[ -]\d{3}[ -]\d{3}(?!\d)"),   # 123 456 789 or 123-456-789
    re.compile(r"(?<!\d)\d{9}(?!\d)"),                       # 123456789
]

# Account pattern: 7-digit number near a contextual keyword
ACCOUNT_CONTEXT_PATTERN = re.compile(
    r"(?:Account(?:\s+Number)?|Acct|Compte|No\.\s*de\s*compte)"
    r"\s*:?\s*\[?(\d{7})\]?",
    re.IGNORECASE,
)

# Fallback: bare 7-digit number on its own (use word boundaries)
ACCOUNT_BARE_PATTERN = re.compile(r"\b(\d{7})\b")

# Keywords that indicate an account number context in surrounding text
ACCOUNT_LINE_KEYWORDS = re.compile(
    r"account|acct|compte|sender|receiver|beneficiary|recipient",
    re.IGNORECASE,
)


def detect_sin(text: str) -> list[PIISpan]:
    """Find Canadian SIN numbers in text using regex + Luhn validation."""
    spans = []
    seen_positions = set()

    for pattern in SIN_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            candidate = match.group(0)

            # Skip if we already found a SIN at this position
            if start in seen_positions:
                continue

            # Validate with Luhn
            if validate_sin(candidate):
                spans.append(PIISpan(
                    entity_type="SIN",
                    text=candidate,
                    start_char=start,
                    end_char=end,
                    confidence=0.95,
                    original_type="CUSTOM_REGEX_SIN",
                ))
                seen_positions.add(start)

    return spans


def detect_account(text: str) -> list[PIISpan]:
    """Find 7-digit Canadian account numbers in text using contextual regex."""
    spans = []
    seen_positions = set()

    # First pass: context-aware matches (high confidence)
    for match in ACCOUNT_CONTEXT_PATTERN.finditer(text):
        acct_num = match.group(1)
        # Find the actual position of the 7-digit group within the full match
        acct_start = match.start() + match.group(0).index(acct_num)
        acct_end = acct_start + len(acct_num)

        spans.append(PIISpan(
            entity_type="ACCOUNT",
            text=acct_num,
            start_char=acct_start,
            end_char=acct_end,
            confidence=0.95,
            original_type="CUSTOM_REGEX_ACCOUNT",
        ))
        seen_positions.add(acct_start)

    # Second pass: bare 7-digit numbers on lines with account-related keywords
    for match in ACCOUNT_BARE_PATTERN.finditer(text):
        start = match.start()
        if start in seen_positions:
            continue

        acct_num = match.group(1)
        # Check if the surrounding line has account-related context
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", start)
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end]

        if ACCOUNT_LINE_KEYWORDS.search(line):
            spans.append(PIISpan(
                entity_type="ACCOUNT",
                text=acct_num,
                start_char=match.start(1),
                end_char=match.end(1),
                confidence=0.85,
                original_type="CUSTOM_REGEX_ACCOUNT_CONTEXTUAL",
            ))
            seen_positions.add(start)

    return spans


def enrich_with_custom_entities(text: str, existing_spans: list[PIISpan]) -> list[PIISpan]:
    """Add custom SIN and ACCOUNT spans that don't overlap with existing detections.

    Deduplication: if an existing span already covers the same character range
    with the same entity type, the custom span is skipped.
    """
    custom_spans = detect_sin(text) + detect_account(text)

    # Build a set of (entity_type, start, end) for existing spans
    existing_coverage = {
        (s.entity_type, s.start_char, s.end_char) for s in existing_spans
    }

    enriched = list(existing_spans)
    for cs in custom_spans:
        # Check for overlap with any existing span of the same type
        dominated = False
        for es in existing_spans:
            if es.entity_type != cs.entity_type:
                continue
            # Check character overlap
            overlap_start = max(cs.start_char, es.start_char)
            overlap_end = min(cs.end_char, es.end_char)
            if overlap_end > overlap_start:
                dominated = True
                break
        if not dominated:
            enriched.append(cs)

    return enriched
