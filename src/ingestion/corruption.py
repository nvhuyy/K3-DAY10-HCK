from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from core.utils import write_json


def _rebuild_embedding_text(df: pd.DataFrame) -> pd.Series:
    columns = ("title", "summary", "authors_joined", "categories_joined")
    return df.apply(
        lambda row: " \n\n".join(
            str(row[column]).strip()
            for column in columns
            if column in row and pd.notna(row[column]) and str(row[column]).strip()
        ),
        axis=1,
    )


def corrupt_clean_dataframe(
    df: pd.DataFrame,
    output_log_path: str | Path,
    target_paper_ids: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Create a deterministic, controlled corruption of a clean paper dataframe.

    Frozen-test document IDs can be supplied so the experiment is guaranteed to
    affect documents which are actually evaluated.  The input dataframe is never
    mutated.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    required = {"paper_id", "title", "summary", "published", "age_days", "text_for_embedding"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    if df.empty:
        raise ValueError("Cannot corrupt an empty dataframe")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    requested_targets = {str(value) for value in (target_paper_ids or []) if str(value)}
    available_targets = [
        paper_id for paper_id in corrupted["paper_id"].astype(str).tolist() if paper_id in requested_targets
    ]
    # Falling back to the newest records keeps direct use of this helper useful.
    targets = available_targets or corrupted["paper_id"].astype(str).head(min(4, len(corrupted))).tolist()

    # Remove half of the frozen documents. This simulates missing latest records
    # and makes the retrieval impact observable despite exact-title lookup.
    removed_ids = targets[::2]
    corrupted = corrupted[~corrupted["paper_id"].astype(str).isin(removed_ids)].copy()
    surviving_targets = [paper_id for paper_id in targets if paper_id not in removed_ids]
    if not surviving_targets:
        surviving_targets = corrupted["paper_id"].astype(str).head(1).tolist()

    blank_ids = surviving_targets[:1]
    stale_ids = surviving_targets[-1:]
    noise_ids = surviving_targets

    corrupted.loc[corrupted["paper_id"].isin(blank_ids), "summary"] = ""
    corrupted.loc[corrupted["paper_id"].isin(blank_ids), "summary_chars"] = 0

    stale_mask = corrupted["paper_id"].isin(stale_ids)
    corrupted.loc[stale_mask, "published"] = "2000-01-01"
    today = pd.Timestamp(datetime.now().date())
    corrupted.loc[stale_mask, "age_days"] = (today - pd.Timestamp("2000-01-01")).days

    corrupted["text_for_embedding"] = _rebuild_embedding_text(corrupted)
    noise_marker = " !!! CORRUPTED_NOISE_9f3a irrelevant random tokens zxqv 0000 !!!"
    noise_mask = corrupted["paper_id"].isin(noise_ids)
    corrupted.loc[noise_mask, "text_for_embedding"] = (
        corrupted.loc[noise_mask, "text_for_embedding"].astype(str) + noise_marker
    )

    duplicate_ids = surviving_targets[:1]
    duplicate_rows = corrupted[corrupted["paper_id"].isin(duplicate_ids)].copy()
    corrupted = pd.concat([corrupted, duplicate_rows], ignore_index=True)

    log = {
        "seed": 10,
        "source_rows": int(len(df)),
        "corrupted_rows": int(len(corrupted)),
        "requested_frozen_target_ids": sorted(requested_targets),
        "affected_frozen_target_ids": sorted(set(targets)),
        "overlaps_frozen_test_set": bool(requested_targets.intersection(targets)),
        "operations": [
            {"scenario": "drop_records", "paper_ids": removed_ids, "count": len(removed_ids)},
            {"scenario": "blank_summary", "paper_ids": blank_ids, "count": len(blank_ids)},
            {"scenario": "stale_date", "paper_ids": stale_ids, "count": len(stale_ids), "value": "2000-01-01"},
            {"scenario": "add_noise", "paper_ids": noise_ids, "count": len(noise_ids), "marker": noise_marker.strip()},
            {"scenario": "duplicate", "paper_ids": duplicate_ids, "count": int(len(duplicate_rows))},
        ],
    }
    write_json(Path(output_log_path), log)
    return corrupted.reset_index(drop=True)
