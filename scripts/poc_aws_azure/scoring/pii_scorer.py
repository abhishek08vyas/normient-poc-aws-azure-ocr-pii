"""PII scoring module — matches detected spans against ground truth and computes metrics."""

import json
import logging
from pathlib import Path

logger = logging.getLogger("poc")

ENTITY_TYPES = ["SIN", "ACCOUNT", "PERSON", "EMAIL", "PHONE", "POSTAL_CODE"]


def match_spans(detected: list[dict], ground_truth: list[dict]) -> dict:
    """Match detected spans to ground truth spans.

    Returns {
        "true_positives": list of (detected, ground_truth) pairs,
        "false_positives": list of detected spans with no match,
        "false_negatives": list of ground_truth spans with no match,
    }

    Rules:
    - Each ground-truth span can match at most one detected span.
    - Each detected span can match at most one ground-truth span.
    - Greedy matching: sort all candidate matches by overlap ratio
      descending, assign greedily.
    - Entity type must match.
    - Character overlap >= 50%.
    """
    # Build all candidate matches
    candidates = []
    for d_idx, d in enumerate(detected):
        for g_idx, g in enumerate(ground_truth):
            if d["entity_type"] != g["entity_type"]:
                continue
            overlap_start = max(d["start_char"], g["start_char"])
            overlap_end = min(d["end_char"], g["end_char"])
            overlap_length = max(0, overlap_end - overlap_start)
            gt_length = g["end_char"] - g["start_char"]
            if gt_length == 0:
                continue
            ratio = overlap_length / gt_length
            if ratio >= 0.50:
                candidates.append((ratio, d_idx, g_idx))

    # Greedy assignment: highest overlap first
    candidates.sort(key=lambda x: x[0], reverse=True)
    matched_d = set()
    matched_g = set()
    true_positives = []

    for ratio, d_idx, g_idx in candidates:
        if d_idx in matched_d or g_idx in matched_g:
            continue
        true_positives.append((detected[d_idx], ground_truth[g_idx]))
        matched_d.add(d_idx)
        matched_g.add(g_idx)

    false_positives = [d for i, d in enumerate(detected) if i not in matched_d]
    false_negatives = [g for i, g in enumerate(ground_truth) if i not in matched_g]

    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


def compute_metrics(all_results: dict) -> dict:
    """Compute aggregate metrics across all documents.

    Input: {doc_id: {"true_positives": [...], "false_positives": [...], "false_negatives": [...]}}

    Returns per-entity-type recall, overall precision, subset metrics.
    """
    per_entity = {}

    for et in ENTITY_TYPES:
        tp = sum(1 for doc in all_results.values()
                 for d, g in doc["true_positives"] if g["entity_type"] == et)
        fn = sum(1 for doc in all_results.values()
                 for g in doc["false_negatives"] if g["entity_type"] == et)
        per_entity[et] = {
            "recall": tp / (tp + fn) if (tp + fn) > 0 else None,
            "tp": tp,
            "fn": fn,
        }

    # Overall precision
    total_tp = sum(len(doc["true_positives"]) for doc in all_results.values())
    total_fp = sum(len(doc["false_positives"]) for doc in all_results.values())
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else None

    # Subset: French PERSON recall (docs where filename contains "_fr_")
    french_tp = sum(1 for doc_id, doc in all_results.items() if "_fr_" in doc_id
                    for d, g in doc["true_positives"] if g["entity_type"] == "PERSON")
    french_fn = sum(1 for doc_id, doc in all_results.items() if "_fr_" in doc_id
                    for g in doc["false_negatives"] if g["entity_type"] == "PERSON")
    french_person_recall = french_tp / (french_tp + french_fn) if (french_tp + french_fn) > 0 else None

    # Subset: Edge-case SIN recall (docs where filename starts with "edge_")
    edge_tp = sum(1 for doc_id, doc in all_results.items() if doc_id.startswith("edge_")
                  for d, g in doc["true_positives"] if g["entity_type"] == "SIN")
    edge_fn = sum(1 for doc_id, doc in all_results.items() if doc_id.startswith("edge_")
                  for g in doc["false_negatives"] if g["entity_type"] == "SIN")
    edge_sin_recall = edge_tp / (edge_tp + edge_fn) if (edge_tp + edge_fn) > 0 else None

    # Subset: False positives on negative controls
    negative_fp = sum(len(doc["false_positives"]) for doc_id, doc in all_results.items()
                      if doc_id.startswith("procedure_"))

    return {
        "per_entity": per_entity,
        "overall_precision": overall_precision,
        "french_person_recall": french_person_recall,
        "edge_sin_recall": edge_sin_recall,
        "negative_control_fp_count": negative_fp,
    }


def _validate(results_dir: Path, tools: list[str], doc_ids: list[str]):
    """Run validation checks before scoring. Raises RuntimeError on failure."""
    errors = []

    for tool in tools:
        tool_dir = results_dir / "pii" / tool / "raw"

        # 1. Completeness
        for doc_id in doc_ids:
            result_path = tool_dir / f"{doc_id}.json"
            if not result_path.exists():
                errors.append(f"Missing result: {tool}/{doc_id}.json")

        # 3. Non-empty spans: at least 140 of 200 docs should have >= 1 detected span
        docs_with_spans = 0
        for doc_id in doc_ids:
            result_path = tool_dir / f"{doc_id}.json"
            if result_path.exists():
                data = json.loads(result_path.read_text(encoding="utf-8"))
                if len(data.get("detected_spans", [])) >= 1:
                    docs_with_spans += 1
        if docs_with_spans < 100:
            errors.append(f"{tool}: only {docs_with_spans}/200 docs have >= 1 span (expected >= 100)")

        # 4. Latency sanity: no single call > 60s
        for doc_id in doc_ids:
            result_path = tool_dir / f"{doc_id}.json"
            if result_path.exists():
                data = json.loads(result_path.read_text(encoding="utf-8"))
                latency_s = data.get("latency_ms", 0) / 1000
                if latency_s > 60:
                    errors.append(f"{tool}/{doc_id}: latency {latency_s:.1f}s > 60s")

        # 5. Cost sanity: total < $10
        total_cost = 0.0
        for doc_id in doc_ids:
            result_path = tool_dir / f"{doc_id}.json"
            if result_path.exists():
                data = json.loads(result_path.read_text(encoding="utf-8"))
                total_cost += data.get("cost_estimate_usd", 0.0)
        if total_cost > 10.0:
            errors.append(f"{tool}: total cost ${total_cost:.2f} > $10.00")

    if errors:
        for e in errors:
            logger.error("Validation: %s", e)
        raise RuntimeError(f"PII validation failed with {len(errors)} error(s)")


def score_all(results_dir: str, corpus_dir: str) -> dict:
    """Score all PII results against ground truth.

    Returns a dict keyed by tool name, each containing metrics from compute_metrics.
    """
    results_path = Path(results_dir)
    corpus_path = Path(corpus_dir)
    tools = ["comprehend", "azure_language"]

    # Load answers.json
    answers_path = corpus_path / "answers.json"
    answers = json.loads(answers_path.read_text(encoding="utf-8"))
    doc_ids = sorted(answers.keys())

    # Validation
    _validate(results_path, tools, doc_ids)

    all_scores = {}

    for tool in tools:
        tool_dir = results_path / "pii" / tool / "raw"
        all_match_results = {}
        total_cost = 0.0
        total_latency = 0.0
        doc_count = 0

        for doc_id in doc_ids:
            result_path = tool_dir / f"{doc_id}.json"
            data = json.loads(result_path.read_text(encoding="utf-8"))
            total_cost += data.get("cost_estimate_usd", 0.0)
            total_latency += data.get("latency_ms", 0)
            doc_count += 1

            ground_truth = answers[doc_id].get("entities", [])

            # Filter detected spans to only our scored entity types + ADDRESS_RAW
            detected = data.get("detected_spans", [])

            # Keep only spans with entity types we score
            scored_detected = [
                s for s in detected
                if s.get("entity_type") in ENTITY_TYPES
            ]

            match_result = match_spans(scored_detected, ground_truth)
            all_match_results[doc_id] = match_result

        metrics = compute_metrics(all_match_results)
        metrics["total_cost"] = total_cost
        metrics["avg_latency_ms"] = total_latency / doc_count if doc_count else 0

        all_scores[tool] = metrics

    return all_scores
