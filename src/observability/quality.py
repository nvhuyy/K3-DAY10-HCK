from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run basic data quality checks and persist the result as JSON."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    report_path = Path(settings.paths.quality_dir) / report_name
    if "age_days" not in df.columns:
        df = df.copy()
        df["age_days"] = 0

    paper_ids = df["paper_id"].fillna("").astype(str)
    titles = df["title"].fillna("").astype(str)
    summaries = df["summary"].fillna("").astype(str)
    summary_lengths = summaries.str.len()

    completeness = {
        "paper_id": round(float((paper_ids != "").mean()), 4) if not df.empty else 0.0,
        "title": round(float((titles != "").mean()), 4) if not df.empty else 0.0,
        "summary": round(float((summary_lengths >= 20).mean()), 4) if not df.empty else 0.0,
    }
    unique_paper_ids = paper_ids[paper_ids != ""].drop_duplicates()

    report = {
        "report_name": report_name,
        "row_count": int(len(df)),
        "completeness": completeness,
        "uniqueness": {
            "paper_id_unique": bool(len(unique_paper_ids) == len(paper_ids[paper_ids != ""])),
            "duplicate_paper_ids": int(len(paper_ids[paper_ids != ""]) - len(unique_paper_ids)),
        },
        "freshness": {
            "stale_rows": int((df["age_days"] > settings.freshness_threshold_days).sum()),
            "freshness_threshold_days": settings.freshness_threshold_days,
            "max_age_days": int(df["age_days"].max()) if not df.empty else 0,
            "is_fresh": bool((df["age_days"] > settings.freshness_threshold_days).sum() == 0),
        },
    }
    write_json(report_path, report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Summarize freshness using the published date and age_days column."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    report_path = Path(report_path)
    published_values = pd.to_datetime(df["published"], errors="coerce") if "published" in df.columns else pd.Series(dtype="datetime64[ns]")
    if "age_days" not in df.columns:
        df = df.copy()
        df["age_days"] = 0

    latest_published = ""
    oldest_published = ""
    if not published_values.empty and published_values.notna().any():
        latest_published = published_values.dropna().max().strftime("%Y-%m-%d")
        oldest_published = published_values.dropna().min().strftime("%Y-%m-%d")

    stale_rows = int((df["age_days"] > settings.freshness_threshold_days).sum())
    report = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": stale_rows,
        "total_rows": int(len(df)),
        "is_fresh": bool(stale_rows == 0),
    }
    write_json(report_path, report)
    return report
