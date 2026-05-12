<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/AWS-Textract%20%7C%20Comprehend-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white" />
  <img src="https://img.shields.io/badge/Azure-Doc%20Intel%20%7C%20Language-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white" />
</p>

# ☁️ AWS vs Azure: OCR + PII Detection — Head-to-Head POC

> **One corpus. Two clouds. Zero guesswork.**

A production-style proof-of-concept that puts **AWS** and **Azure** through the same gauntlet — running OCR and PII detection on identical synthetic corpora and producing a data-driven comparison report. No opinions, just numbers.

---

## 🎯 Why This Exists

Choosing between AWS and Azure for document processing shouldn't be a coin flip. This POC generates its own test data, runs both providers through the same pipeline, and spits out a scoring matrix so you can make the call backed by **real metrics**.

| Category | 🟠 AWS | 🔵 Azure |
|---|---|---|
| **OCR** | Textract | AI Document Intelligence |
| **PII Detection** | Comprehend (PII) | AI Language — PII Detection |

---

## 🔥 What It Does

```
📄 Generate Corpus  →  🤖 Run Both Clouds  →  📊 Score & Compare  →  📋 Report
```

1. 🏗️ **Generates synthetic test corpora** — PDFs, PNGs, Excel files for OCR + 200 PII-annotated text documents with character-level ground truth
2. ⚡ **Runs both cloud providers** against the exact same corpus using a single CLI
3. 📏 **Scores head-to-head** on accuracy, latency, cost, and data-residency compliance
4. 📋 **Produces a decision-ready report** (`POC_results.md`) with populated scoring matrices

---

## 🏗️ Project Structure

```
scripts/poc-aws-azure/
├── main.py              🎮 CLI entry point (argparse)
├── config.py            ⚙️ Env var loading, SDK client init
├── corpus/              🧪 Synthetic data generators
├── ocr/                 👁️ Textract + Doc Intelligence adapters
├── pii/                 🔒 Comprehend + Azure Language adapters
├── scoring/             📊 OCR & PII scoring, report generation
└── utils/               🛠️ Serialization, logging, text chunking

eval/
├── ocr-corpus/spike-seed/   📑 Generated OCR test files + gold texts
└── redaction-corpus/        🔐 Generated PII documents + answers.json
```

---

## 🚀 Quick Start

### 1️⃣ Set up the environment

```bash
python -m venv .venv-poc
source .venv-poc/bin/activate      # Linux/Mac
.venv-poc\Scripts\activate         # Windows

pip install -r requirements-poc.txt
```

### 2️⃣ Configure credentials

```bash
cp .env.poc.example .env.poc
# Fill in your AWS and Azure credentials
```

### 3️⃣ Generate the test corpus

```bash
python scripts/poc-aws-azure/main.py generate-corpus
```

### 4️⃣ Run OCR and PII detection

```bash
python scripts/poc-aws-azure/main.py ocr     # Runs both Textract & Doc Intelligence
python scripts/poc-aws-azure/main.py pii     # Runs both Comprehend & Azure Language
```

### 5️⃣ Score and generate the report

```bash
python scripts/poc-aws-azure/main.py score-ocr
python scripts/poc-aws-azure/main.py score-pii
python scripts/poc-aws-azure/main.py report   # → results/POC_results.md
```

---

## 📊 Evaluation Metrics

### 👁️ OCR Scoring
| Metric | What It Measures |
|---|---|
| **Token Recall** | % of gold-text tokens correctly extracted |
| **Table Fidelity** | Structural accuracy of extracted tables (1–5) |
| **Bounding Box Quality** | Spatial accuracy of word-level boxes (1–5) |
| **Latency** | Processing time per page |
| **Cost** | Projected cost per 1,000 pages |

### 🔒 PII Detection Scoring
| Metric | What It Measures |
|---|---|
| **Per-Entity Recall** | Detection rate for each PII type (SIN, PERSON, PHONE, EMAIL, etc.) |
| **Overall Precision** | How many detections were actually PII |
| **French Name Handling** | Accuracy on accented Québec-French names |
| **Edge-Case SINs** | Detection of SINs with spaces, dashes, brackets |
| **False Positive Rate** | Noise from negative-control documents |
| **Cost** | Projected cost per 1,000 documents |

---

## 🧪 Test Corpus at a Glance

| Corpus | Files | What's Inside |
|---|---|---|
| **OCR** | 10 files | Clean PDFs, scanned PDFs, PNG screenshots, Excel sheets, multi-column layouts |
| **PII** | 200 docs | Wire transfers, screenshots, Excel exports, procedures (negative control), French docs, edge cases |

All data is **100% synthetic** — generated deterministically with `seed(42)` for full reproducibility.

---

## 🛡️ Key Design Decisions

| Decision | Why |
|---|---|
| 🧪 **Synthetic data only** | Zero risk of exposing real customer data |
| 🇨🇦 **Canadian region** | AWS `ca-central-1`, Azure `canadacentral` — data residency compliance |
| 🎲 **Deterministic generation** | `seed(42)` everywhere — same corpus on every run |
| 💰 **$40 cost guardrail** | Built into the CLI to prevent runaway API spend |
| 🔄 **Idempotent runs** | Re-run safely — already-processed files are skipped |

---

## 📦 Requirements

| Dependency | Purpose |
|---|---|
| Python 3.11+ | Runtime |
| `boto3` | AWS SDK (Textract, Comprehend, S3) |
| `azure-ai-documentintelligence` | Azure OCR |
| `azure-ai-textanalytics` | Azure PII |
| `reportlab` + `Pillow` + `openpyxl` | Corpus generation (PDFs, PNGs, Excel) |
| `pymupdf` | PDF rendering for scanned docs |
| `Faker` | Realistic synthetic PII data |

See [`requirements-poc.txt`](requirements-poc.txt) for pinned versions.

---

<p align="center">

📚 *This project is for **education and learning purposes only**.*

Made with ❤️ by **Abhishek Vyas**

</p>
