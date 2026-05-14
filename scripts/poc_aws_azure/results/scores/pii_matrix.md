| Entity type | Comprehend recall | Azure Language recall |
|---|---|---|
| SIN | 13.0% | 0.0% |
| ACCOUNT | 74.6% | 0.0% |
| PERSON (English+French) | 94.8% | 94.9% |
| EMAIL | 75.0% | 100.0% |
| PHONE | 62.5% | 100.0% |
| POSTAL_CODE | 60.0% | 100.0% |
| **Overall precision** | **99.9%** | **68.9%** |

| Subset | Comprehend | Azure Language |
|---|---|---|
| Edge-case SIN (spaces, dashes) | 0.0% | 0.0% |
| French names with accents | 0.0% | 100.0% |
| False positives on negative controls | 0 | 0 |

| Cost | Comprehend | Azure Language |
|---|---|---|
| Total (200 docs) | $0.2464 | $0.3200 |
| Avg latency (ms) | 273ms | 246ms |
