"""CLI entry point for the AWS vs Azure OCR + PII comparison POC."""

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path for imports
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def cmd_generate_corpus(args):
    """Generate both test corpora (no cloud credentials needed)."""
    print("Generating PII corpus...")
    from scripts.poc_aws_azure.corpus.generate_pii_corpus import main as gen_pii
    gen_pii()

    print("\nGenerating OCR corpus...")
    from scripts.poc_aws_azure.corpus.generate_ocr_corpus import main as gen_ocr
    gen_ocr()

    print("\nCorpus generation complete.")


def cmd_ocr(args):
    """Run OCR comparison."""
    import os
    from pathlib import Path
    from scripts.poc_aws_azure.config import (
        load_config, init_aws_clients, OCR_CORPUS_DIR, RESULTS_DIR,
    )
    from scripts.poc_aws_azure.utils.logging_setup import setup_logging
    from scripts.poc_aws_azure.utils.serialization import save_result

    load_config()
    logger = setup_logging(str(RESULTS_DIR))

    tools_to_run = []
    if args.tool:
        tools_to_run.append(args.tool)
    else:
        tools_to_run.append("textract")
        tools_to_run.append("azure_doc_intel")

    # List all files in OCR corpus
    corpus_files = sorted([
        f for f in OCR_CORPUS_DIR.iterdir()
        if f.is_file() and not f.name.endswith(".gold.txt")
    ])
    logger.info("Found %d files in OCR corpus", len(corpus_files))

    for tool_name in tools_to_run:
        if tool_name == "textract":
            _run_textract(corpus_files, args.force, logger, RESULTS_DIR)
        elif tool_name == "azure_doc_intel":
            _run_azure_doc_intel(corpus_files, args.force, logger, RESULTS_DIR)


def _run_textract(corpus_files, force, logger, results_dir):
    """Run Textract on all corpus files."""
    import os
    from pathlib import Path
    from scripts.poc_aws_azure.config import init_aws_clients
    from scripts.poc_aws_azure.ocr.textract_adapter import TextractAdapter
    from scripts.poc_aws_azure.utils.serialization import save_result

    textract_client, s3_client, _ = init_aws_clients()
    bucket = os.environ["AWS_S3_BUCKET_POC"]
    adapter = TextractAdapter(textract_client, s3_client, bucket)

    output_dir = Path(results_dir) / "ocr" / "textract" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    cumulative_cost = 0.0
    COST_GUARDRAIL = 40.0

    for file_path in corpus_files:
        result_path = output_dir / f"{file_path.stem}.json"

        # Idempotency check
        if result_path.exists() and not force:
            logger.info("SKIP: %s already processed", file_path.name)
            continue

        # Cost guardrail
        if cumulative_cost > COST_GUARDRAIL and not force:
            logger.warning("Cost guardrail reached: $%.2f > $%.2f. Use --force to continue.",
                          cumulative_cost, COST_GUARDRAIL)
            break

        result = adapter.extract(str(file_path))
        save_result(result, str(result_path))
        cumulative_cost += result.cost_estimate_usd

    logger.info("Textract total cost: $%.4f", cumulative_cost)

    # S3 cleanup: verify no objects remain under poc-input/
    from botocore.exceptions import ClientError
    try:
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix="poc-input/")
        remaining = response.get("Contents", [])
        if remaining:
            logger.warning("Found %d remaining S3 objects under poc-input/, cleaning up...", len(remaining))
            for obj in remaining:
                s3_client.delete_object(Bucket=bucket, Key=obj["Key"])
                logger.debug("Deleted leftover: %s", obj["Key"])
        else:
            logger.info("S3 cleanup verified: no objects under poc-input/")
    except ClientError as e:
        logger.warning("Could not verify S3 cleanup: %s", e)


def _run_azure_doc_intel(corpus_files, force, logger, results_dir):
    """Run Azure Document Intelligence on all corpus files."""
    from pathlib import Path
    from scripts.poc_aws_azure.config import init_azure_clients
    from scripts.poc_aws_azure.ocr.doc_intel_adapter import DocIntelAdapter
    from scripts.poc_aws_azure.utils.serialization import save_result

    doc_intel_client, _ = init_azure_clients()
    adapter = DocIntelAdapter(doc_intel_client)

    output_dir = Path(results_dir) / "ocr" / "azure_doc_intel" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    cumulative_cost = 0.0
    COST_GUARDRAIL = 40.0

    for file_path in corpus_files:
        result_path = output_dir / f"{file_path.stem}.json"

        # Idempotency check
        if result_path.exists() and not force:
            logger.info("SKIP: %s already processed (azure_doc_intel)", file_path.name)
            continue

        # Cost guardrail
        if cumulative_cost > COST_GUARDRAIL and not force:
            logger.warning("Cost guardrail reached: $%.2f > $%.2f. Use --force to continue.",
                          cumulative_cost, COST_GUARDRAIL)
            break

        result = adapter.extract(str(file_path))
        save_result(result, str(result_path))
        cumulative_cost += result.cost_estimate_usd

    logger.info("Azure Doc Intel total cost: $%.4f", cumulative_cost)


def cmd_pii(args):
    """Run PII detection comparison."""
    from pathlib import Path
    from scripts.poc_aws_azure.config import (
        load_config, init_aws_clients, PII_CORPUS_DIR, RESULTS_DIR,
    )
    from scripts.poc_aws_azure.utils.logging_setup import setup_logging
    from scripts.poc_aws_azure.utils.serialization import save_result

    load_config()
    logger = setup_logging(str(RESULTS_DIR))

    tools_to_run = []
    if args.tool:
        tools_to_run.append(args.tool)
    else:
        tools_to_run.append("comprehend")
        tools_to_run.append("azure_language")

    # List all .txt files in PII corpus
    corpus_files = sorted(PII_CORPUS_DIR.glob("*.txt"))
    logger.info("Found %d PII documents", len(corpus_files))

    for tool_name in tools_to_run:
        if tool_name == "comprehend":
            _run_comprehend(corpus_files, args.force, logger, RESULTS_DIR)
        elif tool_name == "azure_language":
            _run_azure_language(corpus_files, args.force, logger, RESULTS_DIR)


def _run_comprehend(corpus_files, force, logger, results_dir):
    """Run AWS Comprehend PII on all corpus files."""
    from pathlib import Path
    from scripts.poc_aws_azure.config import init_aws_clients
    from scripts.poc_aws_azure.pii.comprehend_adapter import ComprehendAdapter
    from scripts.poc_aws_azure.utils.serialization import save_result

    _, _, comprehend_client = init_aws_clients()
    adapter = ComprehendAdapter(comprehend_client)

    output_dir = Path(results_dir) / "pii" / "comprehend" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    cumulative_cost = 0.0
    COST_GUARDRAIL = 40.0
    processed = 0
    errors = 0

    for file_path in corpus_files:
        doc_id = file_path.stem
        result_path = output_dir / f"{doc_id}.json"

        # Idempotency check
        if result_path.exists() and not force:
            logger.debug("SKIP: %s already processed (comprehend)", doc_id)
            continue

        # Cost guardrail
        if cumulative_cost > COST_GUARDRAIL and not force:
            logger.warning("Cost guardrail reached: $%.2f > $%.2f. Use --force to continue.",
                          cumulative_cost, COST_GUARDRAIL)
            break

        # Parse language from filename (second segment)
        parts = doc_id.split("_")
        language = parts[1] if len(parts) >= 2 else "en"

        text = file_path.read_text(encoding="utf-8")
        result = adapter.detect(text, doc_id, language)
        save_result(result, str(result_path))
        cumulative_cost += result.cost_estimate_usd
        processed += 1
        if result.error:
            errors += 1

    logger.info("Comprehend: processed %d docs, %d errors, total cost $%.4f",
                processed, errors, cumulative_cost)


def _run_azure_language(corpus_files, force, logger, results_dir):
    """Run Azure Language PII on all corpus files."""
    from pathlib import Path
    from scripts.poc_aws_azure.config import init_azure_clients
    from scripts.poc_aws_azure.pii.azure_lang_adapter import AzureLanguageAdapter
    from scripts.poc_aws_azure.utils.serialization import save_result

    _, text_analytics_client = init_azure_clients()
    adapter = AzureLanguageAdapter(text_analytics_client)

    output_dir = Path(results_dir) / "pii" / "azure_language" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    cumulative_cost = 0.0
    COST_GUARDRAIL = 40.0
    processed = 0
    errors = 0

    for file_path in corpus_files:
        doc_id = file_path.stem
        result_path = output_dir / f"{doc_id}.json"

        # Idempotency check
        if result_path.exists() and not force:
            logger.debug("SKIP: %s already processed (azure_language)", doc_id)
            continue

        # Cost guardrail
        if cumulative_cost > COST_GUARDRAIL and not force:
            logger.warning("Cost guardrail reached: $%.2f > $%.2f. Use --force to continue.",
                          cumulative_cost, COST_GUARDRAIL)
            break

        # Parse language from filename (second segment)
        parts = doc_id.split("_")
        language = parts[1] if len(parts) >= 2 else "en"

        text = file_path.read_text(encoding="utf-8")
        result = adapter.detect(text, doc_id, language)
        save_result(result, str(result_path))
        cumulative_cost += result.cost_estimate_usd
        processed += 1
        if result.error:
            errors += 1

    logger.info("Azure Language: processed %d docs, %d errors, total cost $%.4f",
                processed, errors, cumulative_cost)


def cmd_score_ocr(args):
    """Score OCR results."""
    import json
    from scripts.poc_aws_azure.config import load_config, OCR_CORPUS_DIR, RESULTS_DIR
    from scripts.poc_aws_azure.utils.logging_setup import setup_logging
    from scripts.poc_aws_azure.scoring.ocr_scorer import score_all

    load_config()
    logger = setup_logging(str(RESULTS_DIR))

    logger.info("Scoring OCR results...")
    scores = score_all(str(RESULTS_DIR), str(OCR_CORPUS_DIR))

    # Write JSON output
    scores_dir = RESULTS_DIR / "scores"
    scores_dir.mkdir(parents=True, exist_ok=True)

    json_path = scores_dir / "ocr_matrix.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s", json_path)

    # Write markdown output
    md_lines = []
    md_lines.append("| Metric | AWS Textract | Azure Doc Intelligence | Delta |")
    md_lines.append("|---|---|---|---|")

    t = scores.get("textract", {})
    a = scores.get("azure_doc_intel", {})

    categories = [
        ("Recall — clean text PDFs (avg %)", "clean_text_pdf"),
        ("Recall — scanned PDFs (avg %)", "scanned_pdf"),
        ("Recall — screenshots (avg %)", "screenshot"),
        ("Recall — multi-column PDFs (avg %)", "multicolumn_pdf"),
    ]

    for label, cat in categories:
        t_val = t.get("per_category", {}).get(cat, {}).get("recall", 0.0) * 100
        a_val = a.get("per_category", {}).get(cat, {}).get("recall", 0.0) * 100
        delta = t_val - a_val
        md_lines.append(f"| {label} | {t_val:.1f}% | {a_val:.1f}% | {delta:+.1f}% |")

    t_overall = t.get("overall_recall", 0.0) * 100
    a_overall = a.get("overall_recall", 0.0) * 100
    md_lines.append(f"| **Recall — overall (avg %)** | **{t_overall:.1f}%** | **{a_overall:.1f}%** | **{t_overall - a_overall:+.1f}%** |")

    t_lat = t.get("avg_latency_s_per_page", 0.0)
    a_lat = a.get("avg_latency_s_per_page", 0.0)
    md_lines.append(f"| Latency (avg s/page) | {t_lat:.2f}s | {a_lat:.2f}s | {t_lat - a_lat:+.2f}s |")

    t_cost = t.get("avg_cost_per_1k_pages", 0.0)
    a_cost = a.get("avg_cost_per_1k_pages", 0.0)
    md_lines.append(f"| Cost ($/1,000 pages) | ${t_cost:.2f} | ${a_cost:.2f} | ${t_cost - a_cost:+.2f} |")

    t_tf = t.get("avg_table_fidelity", 0.0)
    a_tf = a.get("avg_table_fidelity", 0.0)
    md_lines.append(f"| Table fidelity (avg 1-5) | {t_tf:.1f} | {a_tf:.1f} | {t_tf - a_tf:+.1f} |")

    t_bq = t.get("avg_bbox_quality", 0.0)
    a_bq = a.get("avg_bbox_quality", 0.0)
    md_lines.append(f"| Bbox quality (avg 1-5) | {t_bq:.1f} | {a_bq:.1f} | {t_bq - a_bq:+.1f} |")

    t_err = f"{t.get('errors', 0)} / {t.get('unsupported', 0)}"
    a_err = f"{a.get('errors', 0)} / {a.get('unsupported', 0)}"
    md_lines.append(f"| Errors / unsupported | {t_err} | {a_err} | |")

    md_text = "\n".join(md_lines) + "\n"
    md_path = scores_dir / "ocr_matrix.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)
    logger.info("Wrote %s", md_path)

    # Print summary to console
    print("\n=== OCR Scoring Matrix ===\n")
    print(md_text)


def cmd_score_pii(args):
    """Score PII results."""
    import json
    from scripts.poc_aws_azure.config import load_config, PII_CORPUS_DIR, RESULTS_DIR
    from scripts.poc_aws_azure.utils.logging_setup import setup_logging
    from scripts.poc_aws_azure.scoring.pii_scorer import score_all

    load_config()
    logger = setup_logging(str(RESULTS_DIR))

    logger.info("Scoring PII results...")
    scores = score_all(str(RESULTS_DIR), str(PII_CORPUS_DIR))

    # Write JSON output
    scores_dir = RESULTS_DIR / "scores"
    scores_dir.mkdir(parents=True, exist_ok=True)

    json_path = scores_dir / "pii_matrix.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s", json_path)

    # Write markdown output
    c = scores.get("comprehend", {})
    a = scores.get("azure_language", {})
    c_ent = c.get("per_entity", {})
    a_ent = a.get("per_entity", {})

    def fmt_recall(val):
        return f"{val * 100:.1f}%" if val is not None else "N/A"

    def fmt_prec(val):
        return f"{val * 100:.1f}%" if val is not None else "N/A"

    # Main entity table
    md_lines = []
    md_lines.append("| Entity type | Comprehend recall | Azure Language recall |")
    md_lines.append("|---|---|---|")

    for et in ["SIN", "ACCOUNT", "PERSON", "EMAIL", "PHONE", "POSTAL_CODE"]:
        c_r = fmt_recall(c_ent.get(et, {}).get("recall"))
        a_r = fmt_recall(a_ent.get(et, {}).get("recall"))
        label = et
        if et == "PERSON":
            label = "PERSON (English+French)"
        md_lines.append(f"| {label} | {c_r} | {a_r} |")

    c_prec = fmt_prec(c.get("overall_precision"))
    a_prec = fmt_prec(a.get("overall_precision"))
    md_lines.append(f"| **Overall precision** | **{c_prec}** | **{a_prec}** |")

    md_lines.append("")
    md_lines.append("| Subset | Comprehend | Azure Language |")
    md_lines.append("|---|---|---|")
    md_lines.append(f"| Edge-case SIN (spaces, dashes) | {fmt_recall(c.get('edge_sin_recall'))} | {fmt_recall(a.get('edge_sin_recall'))} |")
    md_lines.append(f"| French names with accents | {fmt_recall(c.get('french_person_recall'))} | {fmt_recall(a.get('french_person_recall'))} |")
    md_lines.append(f"| False positives on negative controls | {c.get('negative_control_fp_count', 0)} | {a.get('negative_control_fp_count', 0)} |")

    md_lines.append("")
    md_lines.append(f"| Cost | Comprehend | Azure Language |")
    md_lines.append(f"|---|---|---|")
    md_lines.append(f"| Total (200 docs) | ${c.get('total_cost', 0):.4f} | ${a.get('total_cost', 0):.4f} |")
    md_lines.append(f"| Avg latency (ms) | {c.get('avg_latency_ms', 0):.0f}ms | {a.get('avg_latency_ms', 0):.0f}ms |")

    md_text = "\n".join(md_lines) + "\n"
    md_path = scores_dir / "pii_matrix.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)
    logger.info("Wrote %s", md_path)

    # Print summary
    print("\n=== PII Scoring Matrix ===\n")
    print(md_text)


def cmd_report(args):
    """Generate final comparison report."""
    import json
    from scripts.poc_aws_azure.config import load_config, RESULTS_DIR
    from scripts.poc_aws_azure.utils.logging_setup import setup_logging
    from scripts.poc_aws_azure.scoring.matrix import generate_report

    load_config()
    logger = setup_logging(str(RESULTS_DIR))

    scores_dir = RESULTS_DIR / "scores"
    ocr_path = scores_dir / "ocr_matrix.json"
    pii_path = scores_dir / "pii_matrix.json"

    if not ocr_path.exists():
        logger.error("Missing %s — run 'score-ocr' first", ocr_path)
        return
    if not pii_path.exists():
        logger.error("Missing %s — run 'score-pii' first", pii_path)
        return

    ocr_scores = json.loads(ocr_path.read_text(encoding="utf-8"))
    pii_scores = json.loads(pii_path.read_text(encoding="utf-8"))

    report_text = generate_report(ocr_scores, pii_scores)

    report_path = RESULTS_DIR / "POC_results.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info("Report written to %s", report_path)
    print(f"Report written to {report_path}")


def main():
    parser = argparse.ArgumentParser(description="POC: AWS vs Azure OCR + PII comparison")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate-corpus
    subparsers.add_parser("generate-corpus", help="Generate test corpora")

    # ocr
    ocr_parser = subparsers.add_parser("ocr", help="Run OCR comparison")
    ocr_parser.add_argument("--tool", choices=["textract", "azure_doc_intel"],
                           help="Run a single tool (default: both)")
    ocr_parser.add_argument("--force", action="store_true",
                           help="Re-run even if results exist")

    # pii
    pii_parser = subparsers.add_parser("pii", help="Run PII detection comparison")
    pii_parser.add_argument("--tool", choices=["comprehend", "azure_language"],
                           help="Run a single tool (default: both)")
    pii_parser.add_argument("--force", action="store_true",
                           help="Re-run even if results exist / override cost guardrail")

    # score-ocr
    subparsers.add_parser("score-ocr", help="Score OCR results")

    # score-pii
    subparsers.add_parser("score-pii", help="Score PII results")

    # report
    subparsers.add_parser("report", help="Generate final comparison report")

    args = parser.parse_args()

    handlers = {
        "generate-corpus": cmd_generate_corpus,
        "ocr": cmd_ocr,
        "pii": cmd_pii,
        "score-ocr": cmd_score_ocr,
        "score-pii": cmd_score_pii,
        "report": cmd_report,
    }

    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
