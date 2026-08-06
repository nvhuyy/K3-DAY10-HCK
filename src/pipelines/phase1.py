from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

src_root = Path(__file__).resolve().parents[1]
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from core.config import load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


def _token_f1(reference: str, prediction: str) -> float:
    ref_tokens = set(reference.lower().split())
    pred_tokens = set(prediction.lower().split())
    if not ref_tokens or not pred_tokens:
        return 0.0
    overlap = len(ref_tokens & pred_tokens)
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def _judge_answer(question: str, reference: str, prediction: str) -> dict[str, Any]:
    token_f1 = _token_f1(reference, prediction)
    if token_f1 >= 0.95:
        return {"score": 5, "correct": True, "reasoning": "High lexical overlap with the reference answer."}
    if token_f1 >= 0.5:
        return {"score": 3, "correct": True, "reasoning": "Partial lexical overlap with the reference answer."}
    return {"score": 1, "correct": False, "reasoning": "Low lexical overlap with the reference answer."}


def main() -> None:
    """Run the baseline pipeline end to end on cleaned paper data."""
    settings = load_settings()
    run_date = datetime.now()

    records = []
    if settings.paths.raw_records_json.exists() and not settings.refresh_source:
        records = load_raw_records(settings.paths.raw_records_json)
    else:
        try:
            records = fetch_source_records(settings)
        except Exception:
            if settings.paths.raw_records_json.exists():
                records = load_raw_records(settings.paths.raw_records_json)
            else:
                raise

    if not records:
        raise RuntimeError("No records were found to build the baseline pipeline.")

    df = build_clean_dataframe(records, run_date)
    if df.empty:
        raise RuntimeError("The cleaned dataframe is empty; cannot build a baseline pipeline.")

    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(df, settings, embeddings_output_path=settings.paths.embeddings_json)

    if settings.paths.eval_testset.exists() and not settings.refresh_test_set:
        test_set = read_json(settings.paths.eval_testset)
    else:
        test_set = build_test_set(df, settings.paths.eval_testset)

    agent = None
    try:
        agent = build_agent(settings, index)
    except Exception:
        agent = None

    answers: list[dict[str, Any]] = []
    for item in test_set:
        retrieval_result = answer_question(item["question"], settings=settings, index=index)
        answer_text = retrieval_result.answer
        if agent is not None:
            try:
                agent_answer = run_agent_question(agent, item["question"])
                if agent_answer and len(agent_answer.strip()) > 8:
                    answer_text = agent_answer
            except Exception:
                pass

        retrieval_hit = any(doc_id in item["ground_truth_doc_ids"] for doc_id in retrieval_result.retrieved_doc_ids)
        judge = _judge_answer(item["question"], item["ground_truth"], answer_text)
        answers.append(
            {
                "id": item["id"],
                "question_type": item["question_type"],
                "question": item["question"],
                "ground_truth": item["ground_truth"],
                "ground_truth_doc_ids": item["ground_truth_doc_ids"],
                "answer": answer_text,
                "retrieved_doc_ids": retrieval_result.retrieved_doc_ids,
                "retrieved_contexts": retrieval_result.retrieved_contexts,
                "retrieval_hit": retrieval_hit,
                "token_f1": _token_f1(item["ground_truth"], answer_text),
                "judge": judge,
            }
        )

    summary = {
        "samples": len(answers),
        "retrieval_hit_rate": mean(1.0 if item["retrieval_hit"] else 0.0 for item in answers),
        "mean_token_f1": mean(item["token_f1"] for item in answers),
        "judge_accuracy": mean(1.0 if item["judge"]["correct"] else 0.0 for item in answers),
        "mean_judge_score": mean(item["judge"]["score"] for item in answers),
    }

    write_json(settings.paths.baseline_metrics, summary)
    write_json(settings.paths.baseline_answers, answers)

    quality_report = run_data_quality_checks(df, settings, "baseline_quality.json")
    freshness_report = build_freshness_report(df, settings, settings.paths.freshness_report)

    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "raw_records_count": len(records),
        "clean_rows": int(len(df)),
        "collection_name": index.collection_name,
        "test_set_size": len(test_set),
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=summary,
        quality=quality_report,
        freshness=freshness_report,
    )

    print(f"Baseline pipeline completed. Report written to {settings.paths.baseline_report}")
