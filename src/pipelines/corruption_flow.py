from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any
import pandas as pd

src_root = Path(__file__).resolve().parents[1]
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from core.config import load_settings
from core.utils import read_json, write_csv, write_json
from ingestion.crossref import load_raw_records
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe, CorruptionConfig
from retrieval.index import LocalEmbeddingIndex
from retrieval.agent import build_agent, run_agent_question
from retrieval.qa import answer_question
from observability.quality import run_data_quality_checks, build_freshness_report
from observability.reporting import generate_corruption_report
from pipelines.phase1 import _token_f1, _judge_answer


def evaluate_index(index: LocalEmbeddingIndex, test_set: list[dict[str, Any]], settings: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
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
        "retrieval_hit_rate": mean(1.0 if item["retrieval_hit"] else 0.0 for item in answers) if answers else 0.0,
        "mean_token_f1": mean(item["token_f1"] for item in answers) if answers else 0.0,
        "judge_accuracy": mean(1.0 if item["judge"]["correct"] else 0.0 for item in answers) if answers else 0.0,
        "mean_judge_score": mean(item["judge"]["score"] for item in answers) if answers else 0.0,
    }
    
    return summary, answers


def main(seed: int = 42, config: CorruptionConfig | None = None) -> None:
    settings = load_settings()
    run_date = datetime.now()

    # Preflight check
    if not settings.paths.clean_json.exists():
        raise FileNotFoundError(f"Baseline clean data not found: {settings.paths.clean_json}")
    if not settings.paths.eval_testset.exists():
        raise FileNotFoundError(f"Test set not found: {settings.paths.eval_testset}")
    if not settings.paths.raw_records_json.exists():
        raise FileNotFoundError(f"Raw records not found for repair: {settings.paths.raw_records_json}")
    if not settings.paths.baseline_metrics.exists():
        raise FileNotFoundError(f"Baseline metrics not found: {settings.paths.baseline_metrics}")

    print("Loading baseline artifacts...")
    baseline_df = pd.DataFrame(read_json(settings.paths.clean_json))
    test_set = read_json(settings.paths.eval_testset)
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    
    # === CORRUPTION ===
    print("Generating corrupted data...")
    if config is None:
        config = CorruptionConfig(seed=seed)
        
    corrupted_df = corrupt_clean_dataframe(
        df=baseline_df, 
        output_log_path=settings.paths.corruption_log, 
        run_date=run_date, 
        config=config,
        test_set=test_set
    )
    
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    
    print("Building corrupted index...")
    corrupted_index = LocalEmbeddingIndex.build(
        df=corrupted_df, 
        settings=settings, 
        embeddings_output_path=settings.paths.corrupted_embeddings_json
    )
    
    print("Evaluating corrupted index...")
    corrupted_metrics, corrupted_answers = evaluate_index(corrupted_index, test_set, settings)
    write_json(settings.paths.corrupted_metrics, corrupted_metrics)
    write_json(settings.paths.corrupted_answers, corrupted_answers)
    
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted_quality.json")
    corrupted_freshness = build_freshness_report(corrupted_df, settings, settings.paths.quality_dir / "corrupted_freshness.json")
    
    # === REPAIR ===
    print("Repairing from raw data...")
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, run_date)
    
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired_df.to_dict(orient="records"))
    
    print("Building repaired index...")
    repaired_index = LocalEmbeddingIndex.build(
        df=repaired_df, 
        settings=settings, 
        embeddings_output_path=settings.paths.repaired_embeddings_json
    )
    
    print("Evaluating repaired index...")
    repaired_metrics, repaired_answers = evaluate_index(repaired_index, test_set, settings)
    write_json(settings.paths.repaired_metrics, repaired_metrics)
    write_json(settings.paths.repaired_answers, repaired_answers)
    
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired_quality.json")
    repaired_freshness = build_freshness_report(repaired_df, settings, settings.paths.quality_dir / "repaired_freshness.json")
    
    print("Generating comparison reports...")
    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_metrics,
        repaired_metrics=repaired_metrics,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    
    # Calculate recovery metrics
    def calculate_recovery(base, corr, rep):
        try:
            return round((rep - corr) / (base - corr), 4) if (base - corr) != 0 else 0.0
        except Exception:
            return 0.0

    comparison_data = {
        "baseline": baseline_metrics,
        "corrupted": corrupted_metrics,
        "repaired": repaired_metrics,
        "recovery": {
            "retrieval_hit_rate": calculate_recovery(
                baseline_metrics.get("retrieval_hit_rate", 0),
                corrupted_metrics.get("retrieval_hit_rate", 0),
                repaired_metrics.get("retrieval_hit_rate", 0),
            ),
            "mean_token_f1": calculate_recovery(
                baseline_metrics.get("mean_token_f1", 0),
                corrupted_metrics.get("mean_token_f1", 0),
                repaired_metrics.get("mean_token_f1", 0),
            )
        }
    }
    
    write_json(settings.paths.quality_dir.parent / "comparison.json", comparison_data)
    
    print(f"Corruption flow completed. Check {settings.paths.comparison_report}")

