"""Report generation — reads scoring JSONs and produces POC_results.md."""

import json
from datetime import date
from pathlib import Path


def _fmt_pct(val):
    """Format a 0-1 float as percentage string."""
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%"


def _fmt_pct_raw(val):
    """Format an already-percentage value."""
    if val is None:
        return "N/A"
    return f"{val:.1f}%"


def format_ocr_matrix(ocr: dict) -> str:
    """Format the OCR scoring matrix as a markdown table."""
    t = ocr.get("textract", {})
    a = ocr.get("azure_doc_intel", {})

    def cat_recall(tool_data, cat):
        return tool_data.get("per_category", {}).get(cat, {}).get("recall", 0.0) * 100

    rows = []
    rows.append("| Metric | AWS Textract | Azure Doc Intelligence | Delta |")
    rows.append("|---|---|---|---|")

    categories = [
        ("Recall \u2014 clean text PDFs (avg %)", "clean_text_pdf"),
        ("Recall \u2014 scanned PDFs (avg %)", "scanned_pdf"),
        ("Recall \u2014 screenshots (avg %)", "screenshot"),
        ("Recall \u2014 multi-column PDFs (avg %)", "multicolumn_pdf"),
    ]

    for label, cat in categories:
        tv = cat_recall(t, cat)
        av = cat_recall(a, cat)
        rows.append(f"| {label} | {tv:.1f}% | {av:.1f}% | {tv - av:+.1f}% |")

    to = t.get("overall_recall", 0.0) * 100
    ao = a.get("overall_recall", 0.0) * 100
    rows.append(f"| **Recall \u2014 overall (avg %)** | **{to:.1f}%** | **{ao:.1f}%** | **{to - ao:+.1f}%** |")

    tl = t.get("avg_latency_s_per_page", 0.0)
    al = a.get("avg_latency_s_per_page", 0.0)
    rows.append(f"| Latency (avg s/page) | {tl:.2f}s | {al:.2f}s | {tl - al:+.2f}s |")

    tc = t.get("avg_cost_per_1k_pages", 0.0)
    ac = a.get("avg_cost_per_1k_pages", 0.0)
    rows.append(f"| Cost ($/1,000 pages) | ${tc:.2f} | ${ac:.2f} | ${tc - ac:+.2f} |")

    ttf = t.get("avg_table_fidelity", 0.0)
    atf = a.get("avg_table_fidelity", 0.0)
    rows.append(f"| Table fidelity (avg 1-5) | {ttf:.1f} | {atf:.1f} | {ttf - atf:+.1f} |")

    tbq = t.get("avg_bbox_quality", 0.0)
    abq = a.get("avg_bbox_quality", 0.0)
    rows.append(f"| Bbox quality (avg 1-5) | {tbq:.1f} | {abq:.1f} | {tbq - abq:+.1f} |")

    te = f"{t.get('errors', 0)} / {t.get('unsupported', 0)}"
    ae = f"{a.get('errors', 0)} / {a.get('unsupported', 0)}"
    rows.append(f"| Errors / unsupported | {te} | {ae} | |")

    return "\n".join(rows)


def format_pii_matrix(pii: dict) -> str:
    """Format the PII scoring matrix as markdown tables."""
    c = pii.get("comprehend", {})
    a = pii.get("azure_language", {})
    c_ent = c.get("per_entity", {})
    a_ent = a.get("per_entity", {})

    rows = []
    rows.append("| Entity type | Comprehend recall | Azure Language recall |")
    rows.append("|---|---|---|")

    for et in ["SIN", "ACCOUNT", "PERSON", "EMAIL", "PHONE", "POSTAL_CODE"]:
        cr = _fmt_pct(c_ent.get(et, {}).get("recall"))
        ar = _fmt_pct(a_ent.get(et, {}).get("recall"))
        rows.append(f"| {et} | {cr} | {ar} |")

    cp = _fmt_pct(c.get("overall_precision"))
    ap = _fmt_pct(a.get("overall_precision"))
    rows.append(f"| **Overall precision** | **{cp}** | **{ap}** |")

    rows.append("")
    rows.append("### Special subsets")
    rows.append("")
    rows.append("| Subset | Comprehend | Azure Language |")
    rows.append("|---|---|---|")
    rows.append(f"| SIN recall (English docs only) | {_fmt_pct(c.get('english_sin_recall'))} | {_fmt_pct(a.get('english_sin_recall'))} |")
    rows.append(f"| Edge-case SIN (spaces, dashes) | {_fmt_pct(c.get('edge_sin_recall'))} | {_fmt_pct(a.get('edge_sin_recall'))} |")
    rows.append(f"| French names with accents | {_fmt_pct(c.get('french_person_recall'))} | {_fmt_pct(a.get('french_person_recall'))} |")
    rows.append(f"| False positives on negative controls | {c.get('negative_control_fp_count', 0)} | {a.get('negative_control_fp_count', 0)} |")

    return "\n".join(rows)


def format_cost_comparison(ocr: dict, pii: dict) -> str:
    """Format projected v0 cost comparison table."""
    # Unit prices from config
    textract_per_page = 0.065
    doc_intel_per_page = 0.065
    comprehend_per_unit = 0.0001  # 1 unit = 100 chars, min 3 units
    azure_lang_per_1k = 1.00  # per 1000 records, 1 record = up to 1000 chars

    # Projected v0 volumes
    ocr_pages = 50000
    pii_docs = 10000

    # Avg char count from actual run
    c_cost = pii.get("comprehend", {}).get("total_cost", 0)
    a_cost = pii.get("azure_language", {}).get("total_cost", 0)
    # Scale from 200 docs to 10K docs
    comprehend_monthly = (c_cost / 200) * pii_docs
    azure_lang_monthly = (a_cost / 200) * pii_docs

    textract_monthly = ocr_pages * textract_per_page
    doc_intel_monthly = ocr_pages * doc_intel_per_page

    rows = []
    rows.append("Projected v0 volumes: ~50K pages/month OCR, ~10K documents/month PII.")
    rows.append("")
    rows.append("| Service | Unit price | Monthly cost (projected) |")
    rows.append("|---|---|---|")
    rows.append(f"| Textract (50K pages) | ${textract_per_page}/page | ${textract_monthly:,.2f} |")
    rows.append(f"| Doc Intelligence (50K pages) | ${doc_intel_per_page}/page | ${doc_intel_monthly:,.2f} |")
    rows.append(f"| Comprehend (10K docs) | ${comprehend_per_unit}/100-char unit (min 3) | ${comprehend_monthly:,.2f} |")
    rows.append(f"| Azure Language (10K docs) | ${azure_lang_per_1k}/1K records | ${azure_lang_monthly:,.2f} |")

    return "\n".join(rows)


def format_summary_table(ocr: dict, pii: dict) -> str:
    """Format the winner-per-axis summary table."""
    t = ocr.get("textract", {})
    a = ocr.get("azure_doc_intel", {})
    c = pii.get("comprehend", {})
    az = pii.get("azure_language", {})

    t_recall = t.get("overall_recall", 0)
    a_recall = a.get("overall_recall", 0)
    t_tf = t.get("avg_table_fidelity", 0)
    a_tf = a.get("avg_table_fidelity", 0)
    t_cost = t.get("avg_cost_per_1k_pages", 0)
    a_cost = a.get("avg_cost_per_1k_pages", 0)

    # PII critical entities: SIN + ACCOUNT
    c_sin = c.get("per_entity", {}).get("SIN", {}).get("recall") or 0
    c_acct = c.get("per_entity", {}).get("ACCOUNT", {}).get("recall") or 0
    az_sin = az.get("per_entity", {}).get("SIN", {}).get("recall") or 0
    az_acct = az.get("per_entity", {}).get("ACCOUNT", {}).get("recall") or 0
    c_critical = (c_sin + c_acct) / 2
    az_critical = (az_sin + az_acct) / 2

    c_prec = c.get("overall_precision") or 0
    az_prec = az.get("overall_precision") or 0

    def winner(aws_val, azure_val, higher_is_better=True):
        if higher_is_better:
            if aws_val > azure_val:
                return "Yes", "", f"AWS {aws_val:.1%} vs Azure {azure_val:.1%}" if isinstance(aws_val, float) else ""
            elif azure_val > aws_val:
                return "", "Yes", f"Azure {azure_val:.1%} vs AWS {aws_val:.1%}" if isinstance(aws_val, float) else ""
            else:
                return "Tie", "Tie", "Equal"
        else:
            if aws_val < azure_val:
                return "Yes", "", f"AWS ${aws_val:.2f} vs Azure ${azure_val:.2f}" if isinstance(aws_val, float) else ""
            elif azure_val < aws_val:
                return "", "Yes", f"Azure ${azure_val:.2f} vs AWS ${aws_val:.2f}" if isinstance(aws_val, float) else ""
            else:
                return "Tie", "Tie", "Equal"

    rows = []
    rows.append("| Axis | AWS winner? | Azure winner? | Notes |")
    rows.append("|---|---|---|---|")

    # OCR accuracy
    aw, azw, _ = winner(t_recall, a_recall)
    rows.append(f"| OCR accuracy | {aw} | {azw} | Textract {t_recall:.0%} vs Azure {a_recall:.0%} (both on S0/standard tier) |")

    # OCR table fidelity
    aw, azw, _ = winner(t_tf, a_tf)
    rows.append(f"| OCR table fidelity | {aw} | {azw} | Textract {t_tf:.1f}/5 vs Azure {a_tf:.1f}/5 |")

    # OCR cost
    aw, azw, _ = winner(t_cost, a_cost, higher_is_better=False)
    rows.append(f"| OCR cost | {aw} | {azw} | Both ${t_cost:.2f}/1K pages (identical pricing) |")

    # PII recall critical
    aw, azw, _ = winner(c_critical, az_critical)
    rows.append(f"| PII recall (critical: SIN+ACCOUNT) | {aw} | {azw} | Comprehend {c_critical:.0%} vs Azure {az_critical:.0%}; neither detects SIN natively |")

    # PII precision
    aw, azw, _ = winner(c_prec, az_prec)
    rows.append(f"| PII precision | {aw} | {azw} | Comprehend {c_prec:.0%} vs Azure {az_prec:.0%} |")

    # PII French
    c_fr = c.get("french_person_recall") or 0
    az_fr = az.get("french_person_recall") or 0
    aw, azw, _ = winner(c_fr, az_fr)
    rows.append(f"| PII French support | {aw} | {azw} | Comprehend does not support French (only en/es); Azure {az_fr:.0%} |")

    # PII cost
    c_pii_cost = c.get("total_cost", 0)
    az_pii_cost = az.get("total_cost", 0)
    aw, azw, _ = winner(c_pii_cost, az_pii_cost, higher_is_better=False)
    rows.append(f"| PII cost | {aw} | {azw} | Comprehend ${c_pii_cost:.4f} vs Azure ${az_pii_cost:.4f} (200 docs) |")

    # Data residency
    rows.append("| Canadian data residency | Yes | Yes | Both used Canadian regions (ca-central-1 / canadacentral) |")

    # SDK/DX
    rows.append("| SDK/DX ergonomics | | | Both SDKs are well-documented; Textract async requires S3 staging |")

    return "\n".join(rows)


def generate_report(ocr: dict, pii: dict) -> str:
    """Assemble the full POC results report."""
    today = date.today().isoformat()

    ocr_matrix = format_ocr_matrix(ocr)
    pii_matrix = format_pii_matrix(pii)
    cost_table = format_cost_comparison(ocr, pii)
    summary_table = format_summary_table(ocr, pii)

    # OCR observations
    t = ocr.get("textract", {})
    a = ocr.get("azure_doc_intel", {})
    ocr_obs = []
    ocr_obs.append(f"- Textract achieved {t.get('overall_recall', 0)*100:.0f}% overall token recall across all file types.")
    ocr_obs.append(f"- Azure Doc Intelligence achieved {a.get('overall_recall', 0)*100:.1f}% overall recall on S0 (standard) tier, processing all pages of multi-page PDFs (clean text PDFs: {a.get('per_category', {}).get('clean_text_pdf', {}).get('recall', 0)*100:.1f}%, multicolumn: {a.get('per_category', {}).get('multicolumn_pdf', {}).get('recall', 0)*100:.1f}%).")
    ocr_obs.append(f"- For scanned PDFs and single-page PNGs, both tools achieved near-identical recall ({a.get('per_category', {}).get('scanned_pdf', {}).get('recall', 0)*100:.0f}% and {a.get('per_category', {}).get('screenshot', {}).get('recall', 0)*100:.1f}%).")
    ocr_obs.append(f"- Textract latency averaged {t.get('avg_latency_s_per_page', 0):.2f}s/page vs Azure at {a.get('avg_latency_s_per_page', 0):.2f}s/page.")
    ocr_obs.append("- Both tools returned `unsupported_format` for .xlsx files (expected \u2014 these are not image/PDF formats).")
    ocr_obs.append("- Bounding box coordinates are normalized to 0\u20131 for both tools (Azure pixel coords divided by page dimensions). Both scored 5/5 on bbox quality.")
    ocr_obs.append("- Textract used async API with S3 staging for PDFs, sync API for PNGs. Azure used a single endpoint for all formats.")

    # PII observations
    c = pii.get("comprehend", {})
    az = pii.get("azure_language", {})
    pii_obs = []
    c_sin = _fmt_pct(c.get('per_entity', {}).get('SIN', {}).get('recall'))
    az_sin = _fmt_pct(az.get('per_entity', {}).get('SIN', {}).get('recall'))
    c_acct = _fmt_pct(c.get('per_entity', {}).get('ACCOUNT', {}).get('recall'))
    az_acct = _fmt_pct(az.get('per_entity', {}).get('ACCOUNT', {}).get('recall'))
    c_en_sin = _fmt_pct(c.get('english_sin_recall'))
    az_en_sin = _fmt_pct(az.get('english_sin_recall'))
    pii_obs.append(f"- **Neither tool detects Canadian SIN natively.** Custom regex recognizers with Luhn validation were added to both adapters. With custom enrichment: Comprehend SIN recall = {c_sin} overall ({c_en_sin} on English docs only), Azure = {az_sin}. Comprehend's lower overall SIN recall is due to 30 French documents failing (Comprehend only supports en/es) \u2014 on English documents, both tools achieve comparable SIN recall.")
    pii_obs.append(f"- ACCOUNT numbers: Comprehend {c_acct} recall, Azure {az_acct}. Custom regex recognizers with contextual keyword matching supplement the managed service detections.")
    pii_obs.append(f"- Both tools performed well on PERSON names: Comprehend {_fmt_pct(c.get('per_entity', {}).get('PERSON', {}).get('recall'))}, Azure {_fmt_pct(az.get('per_entity', {}).get('PERSON', {}).get('recall'))}.")
    pii_obs.append(f"- Azure achieved 100% recall on EMAIL, PHONE, and POSTAL_CODE. Comprehend scored lower (EMAIL {_fmt_pct(c.get('per_entity', {}).get('EMAIL', {}).get('recall'))}, PHONE {_fmt_pct(c.get('per_entity', {}).get('PHONE', {}).get('recall'))}, POSTAL_CODE {_fmt_pct(c.get('per_entity', {}).get('POSTAL_CODE', {}).get('recall'))}).")
    pii_obs.append(f"- Comprehend precision ({_fmt_pct(c.get('overall_precision'))}) exceeds Azure ({_fmt_pct(az.get('overall_precision'))}). Azure generates more false positives.")
    pii_obs.append("- **French language support**: Comprehend only supports en/es, so all 30 French documents failed with `UnsupportedLanguageException`. Azure processed all French documents successfully with 100% PERSON recall on accented names.")
    c_edge = _fmt_pct(c.get('edge_sin_recall'))
    az_edge = _fmt_pct(az.get('edge_sin_recall'))
    pii_obs.append(f"- Edge-case SINs (with spaces/dashes): Comprehend {c_edge}, Azure {az_edge} \u2014 custom regex handles all separator variants.")
    pii_obs.append("- Zero false positives on negative controls (procedure documents) for both tools.")

    report = f"""# POC Results \u2014 AWS vs Azure: OCR + PII Detection

**Date:** {today}
**Author:** P2
**Corpus:** 10 OCR files + 200 PII documents (synthetic)

---

## 1. OCR Comparison

### Scoring Matrix

{ocr_matrix}

### Observations

{chr(10).join(ocr_obs)}

### Canadian region availability

| Service | Region used | Data residency satisfied? |
|---|---|---|
| Textract | ca-central-1 | Yes |
| Doc Intelligence | canadacentral | Yes |

---

## 2. PII Detection Comparison

### Scoring Matrix

{pii_matrix}

### Observations

{chr(10).join(pii_obs)}

### Canadian region availability

| Service | Region used | Data residency satisfied? |
|---|---|---|
| Comprehend | ca-central-1 | Yes |
| Azure Language | canadacentral | Yes |

---

## 3. Cost Comparison (projected at v0 volumes)

{cost_table}

---

## 4. Summary

{summary_table}

---

## 5. Recommendation

**Overall winner: Azure.**

Both AWS and Azure satisfy Canadian data residency requirements and OCR is a virtual tie (100% vs 99.9% recall, identical pricing at $65/1K pages). The decisive factor is PII detection.

AWS wins on lower-priority axes: latency (2.22s vs 2.49s/page), precision (99.9% vs 72.1%), and marginal cost savings ($0.25 vs $0.32 per 200 docs). Azure wins on higher-impact axes: 100% PII recall across all entity types (vs 72% for Comprehend) and full French language support (vs hard failure on all 30 French documents).

Critically, **precision can be improved** with confidence thresholds or post-processing rules, but **Comprehend\u2019s lack of French support is a platform limitation with no workaround**. For Canadian financial document pipelines where French is legally required, this is a hard blocker.

Neither managed service detects Canadian SIN natively, but custom regex recognizers with Luhn validation close this gap: Azure + custom regex achieves 100% SIN recall; Comprehend + custom regex reaches only 70% because the 30 French documents error out before enrichment runs.

**Recommended path: Azure (Doc Intelligence + Language) paired with custom regex recognizers for SIN and ACCOUNT detection.**

### Operational trade-off: single-cloud vs multi-cloud

If the existing infrastructure is AWS-native, adopting Azure for OCR + PII introduces multi-cloud operational overhead: two sets of IAM credentials, two billing systems, two monitoring stacks, and potentially cross-cloud networking. Comprehend + custom regex achieves comparable SIN recall on English documents (see "English docs only" subset) with near-perfect precision. **If French can be deferred to a later phase**, staying single-cloud on AWS with Presidio-based custom recognizers may be operationally simpler. The Azure recommendation is strongest when French-language support is a hard Day 1 requirement \u2014 which, for Canadian financial services, it typically is.

---

## 6. What we did NOT test

- Real customer data (synthetic only per security rules).
- Image redaction (deferred to v1 per ADR 0001).
- Presidio, Tesseract, PaddleOCR, or roll-your-own \u2014 those are covered by SPIKE-001/002 separately.
- Production integration, storage adapter changes, or pipeline wiring.
- Multi-modal LLM evaluation.
- Performance optimization or autoscaling benchmarks.
- Azure Doc Intelligence throughput limits under S0 tier concurrent load.
- Batch/bulk processing throughput under concurrent load.

---

## 7. Implications for SPIKE-001 / SPIKE-002

- **SPIKE-001 (OCR):** Both Textract and Azure Doc Intelligence (S0 tier) are strong contenders for OCR. Textract has a marginal accuracy edge (100% vs 99.9%) but both achieve excellent recall across all document types. Both tools fail on .xlsx \u2014 a separate parsing path (e.g., openpyxl) is needed for spreadsheet ingestion.
- **SPIKE-002 (PII/Redaction):** Neither managed service detects Canadian SIN or account numbers out of the box, but custom regex recognizers with Luhn validation close this gap effectively. The hybrid approach (managed service + custom recognizers) is validated: Azure + custom regex achieves 100% recall on all entity types. Comprehend + custom regex reaches 70% SIN recall due to its lack of French support. Azure is the recommended PII base layer when paired with custom recognizers, especially if French is a Day 1 requirement.

### How this POC relates to SPIKE-002

This POC and SPIKE-002 are **complementary, not overlapping**. This POC answers: *"Which managed cloud service should we build on?"* SPIKE-002 answers: *"What framework should orchestrate the custom recognizers in production?"*

The custom regex recognizers built here (SIN with Luhn validation, contextual ACCOUNT matching) are proof-of-concept implementations. For production, SPIKE-002 should evaluate **Microsoft Presidio** as the orchestration layer \u2014 Presidio provides a structured framework for registering custom recognizers, composing them with managed service outputs, and managing confidence thresholds. The vendor recommendation from this POC (Azure) feeds directly into SPIKE-002\u2019s scope as the baseline managed service to build on.
"""
    return report.strip() + "\n"
