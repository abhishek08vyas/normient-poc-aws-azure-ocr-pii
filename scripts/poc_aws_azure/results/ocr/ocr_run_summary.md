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

## Azure Document Intelligence — S0 tier (Sprint 7, re-run)

| File | Pages | Chars | Latency | Cost |
|---|---|---|---|---|
| clean_policy_01.pdf | 10 | 4,484 | 6,944ms | $0.6500 |
| clean_policy_02.pdf | 10 | 4,476 | 6,455ms | $0.6500 |
| multicolumn_control_09.pdf | 6 | 8,715 | 6,581ms | $0.3900 |
| multicolumn_control_10.pdf | 6 | 8,724 | 6,469ms | $0.3900 |
| scanned_approval_03.pdf | 2 | 236 | 5,376ms | $0.1300 |
| scanned_approval_04.pdf | 2 | 235 | 9,639ms | $0.1300 |
| screenshot_banking_05.png | 1 | 937 | 8,601ms | $0.0650 |
| screenshot_banking_06.png | 1 | 935 | 4,313ms | $0.0650 |
| transactions_07.xlsx | - | - | - | unsupported_format |
| transactions_08.xlsx | - | - | - | unsupported_format |

**Total cost: $2.47**

S0 (standard) tier processes all pages of multi-page PDFs without truncation.

## Observations

- Both tools processed all pages of multi-page PDFs on S0/standard tier.
- Both tools returned `unsupported_format` for .xlsx files (expected).
- Textract used async API with S3 for PDFs, sync API for PNGs.
- Azure latency averaged ~6.5s for PDFs, with some variance on PNGs (4-9s).
- Both tools extracted comparable character counts across all document types.
- Character counts match closely between Textract and Azure for the same files.
