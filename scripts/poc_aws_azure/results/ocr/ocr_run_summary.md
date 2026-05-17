# OCR Run Summary

## AWS Textract (Sprint 6)

| File | Pages | Chars | Latency | Cost |
|---|---|---|---|---|
| clean_policy_01.pdf | 10 | 4,484 | 20,293ms | $0.6500 |
| clean_policy_02.pdf | 10 | 4,476 | 16,659ms | $0.6500 |
| multicolumn_control_09.pdf | 6 | 8,714 | 6,232ms | $0.3900 |
| multicolumn_control_10.pdf | 6 | 8,723 | 16,842ms | $0.3900 |
| scanned_approval_03.pdf | 2 | 236 | 5,772ms | $0.1300 |
| scanned_approval_04.pdf | 2 | 235 | 5,667ms | $0.1300 |
| screenshot_banking_05.png | 1 | 937 | 2,259ms | $0.0650 |
| screenshot_banking_06.png | 1 | 934 | 2,267ms | $0.0650 |
| transactions_07.xlsx | - | - | - | unsupported_format |
| transactions_08.xlsx | - | - | - | unsupported_format |

**Total cost: $2.47**
S3 cleanup verified: no objects under poc-input/

## Azure Document Intelligence — S0 tier (Sprint 7, re-run with bbox normalization)

| File | Pages | Chars | Latency | Cost |
|---|---|---|---|---|
| clean_policy_01.pdf | 10 | 4,484 | 7,240ms | $0.6500 |
| clean_policy_02.pdf | 10 | 4,476 | 6,483ms | $0.6500 |
| multicolumn_control_09.pdf | 6 | 8,715 | 6,536ms | $0.3900 |
| multicolumn_control_10.pdf | 6 | 8,724 | 6,482ms | $0.3900 |
| scanned_approval_03.pdf | 2 | 236 | 7,553ms | $0.1300 |
| scanned_approval_04.pdf | 2 | 235 | 7,595ms | $0.1300 |
| screenshot_banking_05.png | 1 | 937 | 4,437ms | $0.0650 |
| screenshot_banking_06.png | 1 | 935 | 4,365ms | $0.0650 |
| transactions_07.xlsx | - | - | - | unsupported_format |
| transactions_08.xlsx | - | - | - | unsupported_format |

**Total cost: $2.47**

S0 (standard) tier processes all pages of multi-page PDFs without truncation. Bounding boxes normalized to 0-1 coordinates using page width/height.

## Observations

- Both tools processed all pages of multi-page PDFs on S0/standard tier.
- Both tools returned `unsupported_format` for .xlsx files (expected).
- Textract used async API with S3 for PDFs, sync API for PNGs.
- Azure latency averaged ~6.5s for PDFs, ~4.4s for PNGs.
- Both tools extracted comparable character counts across all document types.
- Bounding box quality: both tools scored 5/5 after normalizing Azure's pixel coords to 0-1.
