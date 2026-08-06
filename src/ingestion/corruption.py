from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ingestion.cleaning import _build_text_for_embedding
from core.utils import write_json


@dataclass(frozen=True)
class CorruptionConfig:
    missing_summary_fraction: float = 0.15
    stale_date_fraction: float = 0.15
    noisy_text_fraction: float = 0.10
    duplicate_fraction: float = 0.10
    drop_fraction: float = 0.10
    stale_years: int = 10
    noise_token: str = "[NOISE]"
    seed: int = 42


def corrupt_clean_dataframe(
    df: pd.DataFrame, 
    output_log_path: Path | str, 
    run_date: datetime,
    config: CorruptionConfig | None = None,
    test_set: list[dict[str, Any]] | None = None
) -> pd.DataFrame:
    if config is None:
        config = CorruptionConfig()
        
    rng = np.random.default_rng(config.seed)
    
    corrupted_df = df.copy()
    original_len = len(df)
    
    operations = []
    summary_counts = {
        "missing_summary_count": 0,
        "stale_date_count": 0,
        "noisy_text_count": 0,
        "duplicate_count": 0,
        "dropped_count": 0
    }
    
    indices = np.arange(original_len)
    
    # 1. Missing summary
    num_missing = int(original_len * config.missing_summary_fraction)
    if num_missing > 0:
        missing_indices = rng.choice(indices, size=num_missing, replace=False)
        for idx in missing_indices:
            loc_idx = corrupted_df.index[idx]
            paper_id = corrupted_df.at[loc_idx, 'paper_id']
            before = corrupted_df.at[loc_idx, 'summary']
            corrupted_df.at[loc_idx, 'summary'] = ""
            corrupted_df.at[loc_idx, 'summary_chars'] = 0
            operations.append({
                "type": "missing_summary",
                "paper_id": paper_id,
                "before_length": len(str(before)) if before else 0,
                "after_length": 0
            })
            summary_counts["missing_summary_count"] += 1
            
    # 2. Stale published date
    num_stale = int(original_len * config.stale_date_fraction)
    if num_stale > 0:
        stale_indices = rng.choice(indices, size=num_stale, replace=False)
        for idx in stale_indices:
            loc_idx = corrupted_df.index[idx]
            paper_id = corrupted_df.at[loc_idx, 'paper_id']
            before_date = corrupted_df.at[loc_idx, 'published']
            
            try:
                date_obj = pd.to_datetime(before_date, utc=False)
                if pd.isna(date_obj):
                    continue
                new_date_obj = date_obj.replace(year=date_obj.year - config.stale_years)
                new_date = new_date_obj.strftime("%Y-%m-%d")
                corrupted_df.at[loc_idx, 'published'] = new_date
                
                age = (pd.to_datetime(run_date) - new_date_obj).days
                corrupted_df.at[loc_idx, 'age_days'] = max(0, age)
                
                operations.append({
                    "type": "stale_date",
                    "paper_id": paper_id,
                    "before": before_date,
                    "after": new_date
                })
                summary_counts["stale_date_count"] += 1
            except Exception:
                pass
                
    # 3. Noisy text
    num_noisy = int(original_len * config.noisy_text_fraction)
    if num_noisy > 0:
        noisy_indices = rng.choice(indices, size=num_noisy, replace=False)
        for idx in noisy_indices:
            loc_idx = corrupted_df.index[idx]
            paper_id = corrupted_df.at[loc_idx, 'paper_id']
            before = corrupted_df.at[loc_idx, 'summary']
            after = f"{before} {config.noise_token} " * 2
            corrupted_df.at[loc_idx, 'summary'] = after
            corrupted_df.at[loc_idx, 'summary_chars'] = len(after)
            
            operations.append({
                "type": "noisy_text",
                "paper_id": paper_id,
                "before_length": len(str(before)) if before else 0,
                "after_length": len(after)
            })
            summary_counts["noisy_text_count"] += 1

    # 4. Duplicate records
    num_dupes = int(original_len * config.duplicate_fraction)
    duplicates_to_add = []
    if num_dupes > 0:
        dupe_indices = rng.choice(indices, size=num_dupes, replace=False)
        for idx in dupe_indices:
            row = corrupted_df.iloc[idx].copy()
            duplicates_to_add.append(row)
            operations.append({
                "type": "duplicate_record",
                "paper_id": row['paper_id']
            })
            summary_counts["duplicate_count"] += 1
            
    if duplicates_to_add:
        dupe_df = pd.DataFrame(duplicates_to_add)
        corrupted_df = pd.concat([corrupted_df, dupe_df], ignore_index=True)

    # 5. Dropped records
    current_len = len(corrupted_df)
    num_drops = int(original_len * config.drop_fraction)
    
    # Priority drop: some records from the test set
    test_set_paper_ids = []
    if test_set:
        for item in test_set:
            test_set_paper_ids.extend(item.get("ground_truth_doc_ids", []))
    
    test_set_paper_ids = list(set(test_set_paper_ids))
    
    if num_drops > 0:
        drop_indices_list = []
        # Try to drop some test set records first
        num_test_set_drops = min(len(test_set_paper_ids), num_drops // 2)
        if num_test_set_drops > 0:
            target_ids_to_drop = rng.choice(test_set_paper_ids, size=num_test_set_drops, replace=False)
            target_indices = corrupted_df[corrupted_df["paper_id"].isin(target_ids_to_drop)].index.tolist()
            # In case some test IDs correspond to duplicates, we only want to drop up to num_test_set_drops rows
            target_indices = target_indices[:num_test_set_drops]
            drop_indices_list.extend(target_indices)
        
        remaining_drops = num_drops - len(drop_indices_list)
        if remaining_drops > 0:
            available_indices = list(set(corrupted_df.index) - set(drop_indices_list))
            if len(available_indices) >= remaining_drops:
                random_drop_indices = rng.choice(available_indices, size=remaining_drops, replace=False)
                drop_indices_list.extend(random_drop_indices)
                
        # Log dropped
        for idx in drop_indices_list:
            paper_id = corrupted_df.loc[idx, 'paper_id']
            operations.append({
                "type": "dropped_record",
                "paper_id": paper_id
            })
            summary_counts["dropped_count"] += 1
            
        corrupted_df = corrupted_df.drop(index=drop_indices_list)
        
    # Rebuild text_for_embedding
    corrupted_df['text_for_embedding'] = corrupted_df.apply(_build_text_for_embedding, axis=1)
    
    # Save log
    log_data = {
        "seed": config.seed,
        "input_row_count": original_len,
        "output_row_count": len(corrupted_df),
        "config": asdict(config),
        "operations": operations,
        "summary": summary_counts
    }
    
    write_json(output_log_path, log_data)
    
    return corrupted_df.reset_index(drop=True)
