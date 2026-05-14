# POC Results — AWS vs Azure: OCR + PII Detection

**Date:** 2026-05-14
**Author:** P2
**Corpus:** 10 OCR files + 200 PII documents (synthetic)

---

## 1. OCR Comparison

### Scoring Matrix

| Metric | AWS Textract | Azure Doc Intelligence | Delta |
|---|---|---|---|
| Recall — clean text PDFs (avg %) | 100.0% | 15.9% | +84.1% |
| Recall — scanned PDFs (avg %) | 100.0% | 100.0% | +0.0% |
| Recall — screenshots (avg %) | 100.0% | 99.5% | +0.5% |
| Recall — multi-column PDFs (avg %) | 100.0% | 37.6% | +62.4% |
| **Recall — overall (avg %)** | **100.0%** | **63.3%** | **+36.7%** |
| Latency (avg s/page) | 2.22s | 6.29s | -4.07s |
| Cost ($/1,000 pages) | $65.00 | $65.00 | $+0.00 |
| Table fidelity (avg 1-5) | 5.0 | 3.0 | +2.0 |
| Bbox quality (avg 1-5) | 5.0 | 1.0 | +4.0 |
| Errors / unsupported | 0 / 2 | 0 / 2 | |

### Observations

- Textract achieved 100% overall token recall across all file types.
- Azure Doc Intelligence achieved 63.3% overall recall. The lower score is primarily due to Azure F0 (free) tier truncating multi-page PDFs to 2 pages (clean text PDFs: 15.9%, multicolumn: 37.6%).
- For 2-page scanned PDFs and single-page PNGs (where page truncation is not a factor), both tools achieved near-identical recall (100% and 99.5%).
- Textract latency averaged 2.22s/page vs Azure at 6.29s/page.
- Both tools returned `unsupported_format` for .xlsx files (expected — these are not image/PDF formats).
- Azure bounding box coordinates are in absolute pixels (not normalized 0–1), which explains the low bbox quality score under our normalized-coordinate heuristic.
- Textract used async API with S3 staging for PDFs, sync API for PNGs. Azure used a single endpoint for all formats.

### Canadian region availability

| Service | Region used | Data residency satisfied? |
|---|---|---|
| Textract | ca-central-1 | Yes |
| Doc Intelligence | canadacentral | Yes |

---

## 2. PII Detection Comparison

### Scoring Matrix

| Entity type | Comprehend recall | Azure Language recall |
|---|---|---|
| SIN | 13.0% | 0.0% |
| ACCOUNT | 74.6% | 0.0% |
| PERSON | 94.8% | 94.9% |
| EMAIL | 75.0% | 100.0% |
| PHONE | 62.5% | 100.0% |
| POSTAL_CODE | 60.0% | 100.0% |
| **Overall precision** | **99.9%** | **68.9%** |

### Special subsets

| Subset | Comprehend | Azure Language |
|---|---|---|
| Edge-case SIN (spaces, dashes) | 0.0% | 0.0% |
| French names with accents | 0.0% | 100.0% |
| False positives on negative controls | 0 | 0 |

### Observations

- **Neither tool detects Canadian SIN natively.** Comprehend maps SSN → SIN with 13% recall (likely partial digit matches); Azure detected 0%. Custom regex is required regardless of vendor.
- Comprehend detected ACCOUNT numbers at 74.6% recall (maps BANK_ACCOUNT → ACCOUNT); Azure did not detect account numbers at all (0%).
- Both tools performed well on PERSON names: Comprehend 94.8%, Azure 94.9%.
- Azure achieved 100% recall on EMAIL, PHONE, and POSTAL_CODE. Comprehend scored lower (EMAIL 75.0%, PHONE 62.5%, POSTAL_CODE 60.0%).
- Comprehend precision (99.9%) far exceeds Azure (68.9%). Azure generates more false positives.
- **French language support**: Comprehend only supports en/es, so all 30 French documents failed with `UnsupportedLanguageException`. Azure processed all French documents successfully with 100% PERSON recall on accented names.
- Edge-case SINs (with spaces/dashes): 0% recall for both tools — confirms that SIN detection requires custom logic.
- Zero false positives on negative controls (procedure documents) for both tools.

### Canadian region availability

| Service | Region used | Data residency satisfied? |
|---|---|---|
| Comprehend | ca-central-1 | Yes |
| Azure Language | canadacentral | Yes |

---

## 3. Cost Comparison (projected at v0 volumes)

Projected v0 volumes: ~50K pages/month OCR, ~10K documents/month PII.

| Service | Unit price | Monthly cost (projected) |
|---|---|---|
| Textract (50K pages) | $0.065/page | $3,250.00 |
| Doc Intelligence (50K pages) | $0.065/page | $3,250.00 |
| Comprehend (10K docs) | $0.0001/100-char unit (min 3) | $12.32 |
| Azure Language (10K docs) | $1.0/1K records | $16.00 |

---

## 4. Summary

| Axis | AWS winner? | Azure winner? | Notes |
|---|---|---|---|
| OCR accuracy | Yes |  | Textract 100% vs Azure 63% (Azure F0 tier truncated multi-page PDFs) |
| OCR table fidelity | Yes |  | Textract 5.0/5 vs Azure 3.0/5 |
| OCR cost | Tie | Tie | Both $65.00/1K pages (identical pricing) |
| PII recall (critical: SIN+ACCOUNT) | Yes |  | Comprehend 44% vs Azure 0%; neither detects SIN natively |
| PII precision | Yes |  | Comprehend 100% vs Azure 69% |
| PII French support |  | Yes | Comprehend does not support French (only en/es); Azure 100% |
| PII cost | Yes |  | Comprehend $0.2464 vs Azure $0.3200 (200 docs) |
| Canadian data residency | Yes | Yes | Both used Canadian regions (ca-central-1 / canadacentral) |
| SDK/DX ergonomics | | | Both SDKs are well-documented; Textract async requires S3 staging |

---

## 5. Recommendation

Both AWS and Azure satisfy Canadian data residency requirements. For OCR, Textract is the stronger choice: it processes all pages of multi-page documents, achieves higher table fidelity, and has lower latency. Azure Doc Intelligence produced comparable results on short documents but was limited by F0 tier page truncation (S0 tier would need re-evaluation). For PII detection, neither tool detects Canadian SIN or account numbers natively — custom regex/Presidio recognizers are required regardless of vendor. Azure has better language coverage (French support) and higher recall on standard entity types (EMAIL, PHONE, POSTAL_CODE), while Comprehend has significantly better precision (fewer false positives). The choice depends on whether recall or precision is prioritized for the v0 pipeline, and whether French-language document support is a Day 1 requirement.

---

## 6. What we did NOT test

- Real customer data (synthetic only per security rules).
- Image redaction (deferred to v1 per ADR 0001).
- Presidio, Tesseract, PaddleOCR, or roll-your-own — those are covered by SPIKE-001/002 separately.
- Production integration, storage adapter changes, or pipeline wiring.
- Multi-modal LLM evaluation.
- Performance optimization or autoscaling benchmarks.
- Azure Doc Intelligence S0 (standard) tier — F0 (free) tier was used, which truncates multi-page PDFs to 2 pages.
- Batch/bulk processing throughput under concurrent load.

---

## 7. Implications for SPIKE-001 / SPIKE-002

- **SPIKE-001 (OCR):** Textract is the clear frontrunner for OCR accuracy and table extraction. Azure Doc Intelligence remains viable but requires S0 tier evaluation for multi-page documents. Both tools fail on .xlsx — a separate parsing path (e.g., openpyxl) is needed for spreadsheet ingestion.
- **SPIKE-002 (PII/Redaction):** Neither managed service detects Canadian SIN or account numbers out of the box. This confirms that a hybrid approach (managed service + custom Presidio recognizers for Canadian-specific entities) is required regardless of cloud vendor. Azure’s French support and higher entity recall make it a better base layer if supplemented with custom recognizers to improve precision. Comprehend’s higher precision makes it a better choice if false positives are costly in the downstream pipeline.
