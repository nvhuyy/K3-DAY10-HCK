from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run the frozen-test corruption, repair, and three-state comparison."""
    settings = load_settings()
    required_paths = (
        settings.paths.clean_csv,
        settings.paths.raw_records_json,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
    )
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Run Phase 1 first; missing artifacts: " + ", ".join(missing))

    clean_df = pd.read_csv(settings.paths.clean_csv, keep_default_na=False)
    test_set = read_json(settings.paths.eval_testset)
    frozen_ids = {
        str(paper_id)
        for item in test_set
        for paper_id in item.get("ground_truth_doc_ids", [])
    }

    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log, frozen_ids)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df, settings, embeddings_output_path=settings.paths.corrupted_embeddings_json
    )
    corrupted = evaluate_pipeline(
        settings,
        corrupted_index,
        settings.paths.eval_testset,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted_quality.json")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, settings.paths.quality_dir / "corrupted_freshness.json"
    )

    # Repair must be reproducible: rebuild exclusively from the C2 raw snapshot,
    # never from the corrupted dataframe or a fresh API response.
    raw_records = load_raw_records(settings.paths.raw_records_json)
    if not raw_records:
        raise RuntimeError("The raw C2 snapshot contains no records; repair is impossible")
    repaired_df = build_clean_dataframe(raw_records, datetime.now())
    if repaired_df.empty:
        raise RuntimeError("Cleaning the raw C2 snapshot produced an empty repair dataset")
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired_df.to_dict(orient="records"))
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df, settings, embeddings_output_path=settings.paths.repaired_embeddings_json
    )
    repaired = evaluate_pipeline(
        settings,
        repaired_index,
        settings.paths.eval_testset,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired_quality.json")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, settings.paths.quality_dir / "repaired_freshness.json"
    )

    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics=read_json(settings.paths.baseline_metrics),
        corrupted_metrics=corrupted.summary,
        repaired_metrics=repaired.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    print(f"Corruption flow completed. Report written to {settings.paths.comparison_report}")
