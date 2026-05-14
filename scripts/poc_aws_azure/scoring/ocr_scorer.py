"""OCR scoring module — compares OCR results against gold text references."""

import json
import logging
import re
import unicodedata
from collections import Counter
from pathlib import Path

logger = logging.getLogger("poc")

OCR_FILE_CATEGORIES = {
    "clean_policy_01": "clean_text_pdf",
    "clean_policy_02": "clean_text_pdf",
    "scanned_approval_03": "scanned_pdf",
    "scanned_approval_04": "scanned_pdf",
    "screenshot_banking_05": "screenshot",
    "screenshot_banking_06": "screenshot",
    "transactions_07": "excel",
    "transactions_08": "excel",
    "multicolumn_control_09": "multicolumn_pdf",
    "multicolumn_control_10": "multicolumn_pdf",
}

# Files where table fidelity scoring applies
TABLE_FIDELITY_FILES = {
    "screenshot_banking_05", "screenshot_banking_06",
    "multicolumn_control_09", "multicolumn_control_10",
}

# Files where bbox quality scoring applies
BBOX_QUALITY_FILES = {
    "scanned_approval_03", "scanned_approval_04",
    "screenshot_banking_05", "screenshot_banking_06",
}

PAGE_MARKER_RE = re.compile(r"^--- PAGE \d+ ---$", re.MULTILINE)


def tokenize(text: str) -> list[str]:
    """Tokenize text for recall comparison.

    Rules:
    - Convert to lowercase.
    - Normalize Unicode (NFC) so accented characters compare correctly.
    - Split on whitespace.
    - Strip leading/trailing punctuation from each token.
    - Keep internal punctuation: "year-end" stays as "year-end".
    - Discard empty tokens after stripping.
    - Numbers are kept as-is.
    """
    text = unicodedata.normalize("NFC", text.lower())
    raw_tokens = text.split()
    result = []
    for t in raw_tokens:
        t = t.strip(
            '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'
            '\u2014\u2013\u2018\u2019\u201c\u201d\u2026'
        )
        if t:
            result.append(t)
    return result


def compute_recall(extracted_text: str, gold_text: str) -> float:
    """Token-level recall: what fraction of gold tokens appear in extracted.

    Uses multiset (Counter) comparison so duplicate tokens are counted
    independently.
    """
    gold_tokens = tokenize(gold_text)
    extracted_tokens = tokenize(extracted_text)

    if not gold_tokens:
        return 1.0

    gold_counts = Counter(gold_tokens)
    extracted_counts = Counter(extracted_tokens)

    matched = sum(
        min(extracted_counts.get(token, 0), count)
        for token, count in gold_counts.items()
    )
    return matched / sum(gold_counts.values())


def extract_gold_tables(gold_text: str) -> list[tuple[int, int, list[str]]]:
    """Extract tables from gold text.

    A table is a sequence of consecutive lines where each line
    contains at least one tab character. Returns list of
    (row_count, col_count, flat_list_of_cell_values).
    """
    lines = gold_text.split("\n")
    tables = []
    current_table_lines = []

    for line in lines:
        if "\t" in line:
            current_table_lines.append(line)
        else:
            if current_table_lines:
                rows = len(current_table_lines)
                cols = max(tl.count("\t") + 1 for tl in current_table_lines)
                cells = []
                for tl in current_table_lines:
                    cells.extend(tl.split("\t"))
                tables.append((rows, cols, cells))
                current_table_lines = []

    # Flush last table
    if current_table_lines:
        rows = len(current_table_lines)
        cols = max(tl.count("\t") + 1 for tl in current_table_lines)
        cells = []
        for tl in current_table_lines:
            cells.extend(tl.split("\t"))
        tables.append((rows, cols, cells))

    return tables


def score_table_fidelity(ocr_tables: list[dict], gold_text: str) -> int:
    """Automated table fidelity scoring (1-5)."""
    gold_tables = extract_gold_tables(gold_text)

    if not gold_tables:
        return 5 if not ocr_tables else 3

    if not ocr_tables:
        return 1

    total_score = 0
    for gold_rows, gold_cols, gold_cells in gold_tables:
        best = 1
        for ocr_table in ocr_tables:
            row_match = 1 - abs(ocr_table["row_count"] - gold_rows) / max(gold_rows, 1)
            col_match = 1 - abs(ocr_table["col_count"] - gold_cols) / max(gold_cols, 1)
            structure_score = (row_match + col_match) / 2

            ocr_cell_texts = {c["text"].strip().lower() for c in ocr_table["cells"]}
            gold_cell_texts = {c.strip().lower() for c in gold_cells if c.strip()}
            if gold_cell_texts:
                content_match = len(ocr_cell_texts & gold_cell_texts) / len(gold_cell_texts)
            else:
                content_match = 1.0

            combined = structure_score * 0.4 + content_match * 0.6

            if combined >= 0.9:
                best = max(best, 5)
            elif combined >= 0.75:
                best = max(best, 4)
            elif combined >= 0.5:
                best = max(best, 3)
            elif combined >= 0.25:
                best = max(best, 2)
            else:
                best = max(best, 1)

        total_score += best

    return round(total_score / len(gold_tables))


def score_bbox_quality(words: list[dict]) -> int:
    """Automated bounding box quality scoring (1-5)."""
    if not words:
        return 1

    total = len(words)
    issues = 0

    for w in words:
        b = w["bbox"]
        if b["width"] <= 0 or b["height"] <= 0:
            issues += 1
            continue
        if b["width"] > 0.3 or b["height"] > 0.1:
            issues += 1
        if b["left"] < 0 or b["top"] < 0 or b["left"] + b["width"] > 1.05 or b["top"] + b["height"] > 1.05:
            issues += 1

    issue_rate = issues / total
    if issue_rate <= 0.02:
        return 5
    elif issue_rate <= 0.10:
        return 4
    elif issue_rate <= 0.20:
        return 3
    elif issue_rate <= 0.40:
        return 2
    else:
        return 1


def _strip_page_markers(gold_text: str) -> str:
    """Remove --- PAGE N --- markers from gold text."""
    return PAGE_MARKER_RE.sub("", gold_text)


def _validate(results_dir: Path, tools: list[str], file_stems: list[str]):
    """Run validation checks before scoring. Raises RuntimeError on failure."""
    errors = []

    # 1. Completeness
    for tool in tools:
        tool_dir = results_dir / "ocr" / tool / "raw"
        for stem in file_stems:
            result_path = tool_dir / f"{stem}.json"
            if not result_path.exists():
                errors.append(f"Missing result: {tool}/{stem}.json")

    # 2. Non-empty text: at least 8 of 10 should have full_text > 100 chars
    for tool in tools:
        tool_dir = results_dir / "ocr" / tool / "raw"
        non_empty = 0
        for stem in file_stems:
            result_path = tool_dir / f"{stem}.json"
            if result_path.exists():
                data = json.loads(result_path.read_text(encoding="utf-8"))
                if len(data.get("full_text", "")) > 100:
                    non_empty += 1
        if non_empty < 8:
            errors.append(f"{tool}: only {non_empty}/10 files have full_text > 100 chars (expected >= 8)")

    # 3. Latency sanity: no single-page > 120s
    for tool in tools:
        tool_dir = results_dir / "ocr" / tool / "raw"
        for stem in file_stems:
            result_path = tool_dir / f"{stem}.json"
            if result_path.exists():
                data = json.loads(result_path.read_text(encoding="utf-8"))
                page_count = max(data.get("page_count", 1), 1)
                latency_s = data.get("latency_ms", 0) / 1000
                if page_count == 1 and latency_s > 120:
                    errors.append(f"{tool}/{stem}: single-page latency {latency_s:.1f}s > 120s")

    # 4. Cost sanity: total < $5
    for tool in tools:
        tool_dir = results_dir / "ocr" / tool / "raw"
        total_cost = 0.0
        for stem in file_stems:
            result_path = tool_dir / f"{stem}.json"
            if result_path.exists():
                data = json.loads(result_path.read_text(encoding="utf-8"))
                total_cost += data.get("cost_estimate_usd", 0.0)
        if total_cost > 5.0:
            errors.append(f"{tool}: total cost ${total_cost:.2f} > $5.00")

    if errors:
        for e in errors:
            logger.error("Validation: %s", e)
        raise RuntimeError(f"OCR validation failed with {len(errors)} error(s)")


def score_all(results_dir: str, corpus_dir: str) -> dict:
    """Score all OCR results against gold files.

    Returns a dict keyed by tool name, each containing per-file scores,
    per-category averages, and overall averages.
    """
    results_path = Path(results_dir)
    corpus_path = Path(corpus_dir)
    tools = ["textract", "azure_doc_intel"]
    file_stems = sorted(OCR_FILE_CATEGORIES.keys())

    # Validation
    _validate(results_path, tools, file_stems)

    # Load gold texts (stripped of page markers)
    gold_texts = {}
    for stem in file_stems:
        gold_file = corpus_path / f"{stem}.gold.txt"
        gold_texts[stem] = _strip_page_markers(gold_file.read_text(encoding="utf-8"))

    all_scores = {}

    for tool in tools:
        tool_dir = results_path / "ocr" / tool / "raw"
        per_file = {}
        category_recalls = {}  # category -> list of recalls
        all_latencies = []
        all_costs = []
        table_fidelities = []
        bbox_qualities = []
        error_count = 0
        unsupported_count = 0

        for stem in file_stems:
            result_path = tool_dir / f"{stem}.json"
            data = json.loads(result_path.read_text(encoding="utf-8"))
            category = OCR_FILE_CATEGORIES[stem]

            file_score = {"file": stem, "category": category}

            # Handle errors / unsupported
            if data.get("error"):
                error_str = data["error"]
                file_score["error"] = error_str
                if "unsupported_format" in error_str:
                    unsupported_count += 1
                    file_score["recall"] = None
                    file_score["excluded"] = True
                else:
                    error_count += 1
                    file_score["recall"] = 0.0
                    if category not in category_recalls:
                        category_recalls[category] = []
                    category_recalls[category].append(0.0)

                per_file[stem] = file_score
                continue

            # Recall
            gold = gold_texts[stem]
            recall = compute_recall(data.get("full_text", ""), gold)
            file_score["recall"] = recall

            if category not in category_recalls:
                category_recalls[category] = []
            category_recalls[category].append(recall)

            # Latency
            page_count = max(data.get("page_count", 1), 1)
            latency_per_page = data.get("latency_ms", 0) / (page_count * 1000)
            file_score["latency_s_per_page"] = latency_per_page
            all_latencies.append(latency_per_page)

            # Cost
            cost_per_1k = (data.get("cost_estimate_usd", 0.0) / page_count) * 1000
            file_score["cost_per_1k_pages"] = cost_per_1k
            all_costs.append(cost_per_1k)

            # Table fidelity (only for applicable files)
            if stem in TABLE_FIDELITY_FILES:
                tf = score_table_fidelity(data.get("tables", []), gold)
                file_score["table_fidelity"] = tf
                table_fidelities.append(tf)

            # Bbox quality (only for applicable files)
            if stem in BBOX_QUALITY_FILES:
                bq = score_bbox_quality(data.get("words", []))
                file_score["bbox_quality"] = bq
                bbox_qualities.append(bq)

            per_file[stem] = file_score

        # Per-category averages
        per_category = {}
        for cat, recalls in category_recalls.items():
            per_category[cat] = {
                "recall": sum(recalls) / len(recalls) if recalls else 0.0,
                "count": len(recalls),
            }

        # Overall recall (exclude unsupported)
        all_recalls = [r for recalls in category_recalls.values() for r in recalls]
        overall_recall = sum(all_recalls) / len(all_recalls) if all_recalls else 0.0

        all_scores[tool] = {
            "per_file": per_file,
            "per_category": per_category,
            "overall_recall": overall_recall,
            "avg_latency_s_per_page": sum(all_latencies) / len(all_latencies) if all_latencies else 0.0,
            "avg_cost_per_1k_pages": sum(all_costs) / len(all_costs) if all_costs else 0.0,
            "avg_table_fidelity": sum(table_fidelities) / len(table_fidelities) if table_fidelities else 0.0,
            "avg_bbox_quality": sum(bbox_qualities) / len(bbox_qualities) if bbox_qualities else 0.0,
            "errors": error_count,
            "unsupported": unsupported_count,
        }

    return all_scores
