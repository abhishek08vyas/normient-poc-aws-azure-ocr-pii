"""PII data contracts, entity normalization, and abstract adapter base."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PIISpan:
    entity_type: str           # normalized: SIN, ACCOUNT, PERSON, EMAIL, PHONE, POSTAL_CODE, AMOUNT
    text: str                  # the detected text
    start_char: int            # char offset in input
    end_char: int              # char offset in input
    confidence: float          # 0.0-1.0
    original_type: str         # vendor's raw entity type before normalization


@dataclass
class PIIResult:
    tool: str                  # "comprehend" | "azure_language"
    doc_id: str                # document identifier (filename without extension)
    detected_spans: list[PIISpan]
    latency_ms: int
    cost_estimate_usd: float
    char_count: int            # input character count
    error: str | None


# Entity type normalization maps
COMPREHEND_TYPE_MAP = {
    "SSN": "SIN",
    "NAME": "PERSON",
    "BANK_ACCOUNT_NUMBER": "ACCOUNT",
    "CREDIT_DEBIT_NUMBER": "ACCOUNT",
    "EMAIL": "EMAIL",
    "PHONE": "PHONE",
    "ADDRESS": "ADDRESS_RAW",  # special handling below
}

AZURE_TYPE_MAP = {
    "USSocialSecurityNumber": "SIN",
    "Person": "PERSON",
    "ABARoutingNumber": "ACCOUNT",
    "SWIFTCode": "ACCOUNT",
    "CreditCardNumber": "ACCOUNT",
    "InternationalBankingAccountNumber": "ACCOUNT",
    "Email": "EMAIL",
    "PhoneNumber": "PHONE",
    "Address": "ADDRESS_RAW",  # special handling below
}

# Postal code extraction regex
POSTAL_CODE_PATTERN = r"[A-Z]\d[A-Z]\s?\d[A-Z]\d"


def normalize_entity_type(raw_type: str, tool: str) -> str:
    """Look up the normalization map for the given tool. Returns normalized type or UNMAPPED:{raw_type}."""
    if tool == "comprehend":
        type_map = COMPREHEND_TYPE_MAP
    elif tool == "azure_language":
        type_map = AZURE_TYPE_MAP
    else:
        return f"UNMAPPED:{raw_type}"

    return type_map.get(raw_type, f"UNMAPPED:{raw_type}")


def extract_postal_from_address(address_text: str, address_start: int) -> "PIISpan | None":
    """If the address contains a Canadian postal code, return a PIISpan for it."""
    match = re.search(POSTAL_CODE_PATTERN, address_text)
    if match:
        postal_text = match.group(0)
        postal_start = address_start + match.start()
        postal_end = address_start + match.end()
        return PIISpan(
            entity_type="POSTAL_CODE",
            text=postal_text,
            start_char=postal_start,
            end_char=postal_end,
            confidence=0.99,
            original_type="ADDRESS_POSTAL_EXTRACTION",
        )
    return None


class PIIAdapter(ABC):
    @abstractmethod
    def detect(self, text: str, doc_id: str, language: str) -> PIIResult:
        """Run PII detection on text and return the result."""
        ...
