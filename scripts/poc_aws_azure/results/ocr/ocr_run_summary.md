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

## Azure Document Intelligence (Sprint 7)

| File | Pages | Chars | Latency | Cost |
|---|---|---|---|---|
| clean_policy_01.pdf | 2* | 717 | 6,555ms | $0.1300 |
| clean_policy_02.pdf | 2* | 706 | 5,294ms | $0.1300 |
| multicolumn_control_09.pdf | 2* | 3,267 | 5,409ms | $0.1300 |
| multicolumn_control_10.pdf | 2* | 3,267 | 5,412ms | $0.1300 |
| scanned_approval_03.pdf | 2 | 236 | 5,358ms | $0.1300 |
| scanned_approval_04.pdf | 2 | 235 | 5,293ms | $0.1300 |
| screenshot_banking_05.png | 1 | 937 | 28,381ms | $0.0650 |
| screenshot_banking_06.png | 1 | 935 | 5,317ms | $0.0650 |
| transactions_07.xlsx | - | - | - | unsupported_format |
| transactions_08.xlsx | - | - | - | unsupported_format |

**Total cost: $0.91**

*Note: Azure F0 (free) tier limits processing to 2 pages per document. Multi-page PDFs (clean_policy 10pg, multicolumn 6pg) were truncated. S0 (standard) tier would process all pages.

## Observations

- Textract processed all pages of multi-page PDFs; Azure F0 tier truncated to 2 pages.
- Both tools returned `unsupported_format` for .xlsx files (expected).
- Textract used async API with S3 for PDFs, sync API for PNGs.
- Azure latency was generally consistent (~5-6s) except for one PNG outlier (28s).
- Textract extracted more characters from multi-page PDFs due to processing all pages.
- For 2-page scanned PDFs and PNGs, both tools produced comparable character counts.
