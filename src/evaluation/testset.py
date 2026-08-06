from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import normalize_whitespace, write_json


def _get_row_value(row: pd.Series, *names: str) -> object | None:
    for name in names:
        if name in row.index:
            value = row[name]
            if value is None or (isinstance(value, float) and pd.isna(value)):
                continue
            return value
    return None


def _as_text(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return normalize_whitespace(str(value))


def _as_list(value: object | None) -> list[str]:
    if isinstance(value, list):
        return [normalize_whitespace(str(item)) for item in value if normalize_whitespace(str(item))]
    if isinstance(value, str):
        text = normalize_whitespace(value)
        return [text] if text else []
    return []


def _select_representative_rows(df: pd.DataFrame, max_rows: int = 4) -> pd.DataFrame:
    if len(df) <= max_rows:
        return df.copy()

    step = max(1, len(df) // max_rows)
    indices: list[int] = []
    for idx in range(0, len(df), step):
        indices.append(idx)
        if len(indices) >= max_rows:
            break
    return df.iloc[indices].copy()


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Tạo bộ evaluation set từ dataframe papers đã làm sạch."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    if df.empty:
        raise ValueError("Cannot build a test set from an empty dataframe")
    if len(df) < 5:
        raise ValueError("At least 5 cleaned papers are required to build a meaningful test set")

    sample_df = _select_representative_rows(df, max_rows=4)
    samples: list[dict[str, Any]] = []

    for index, row in sample_df.iterrows():
        paper_id = _as_text(_get_row_value(row, "paper_id", "id", "doi"))
        title = _as_text(_get_row_value(row, "title"))
        summary = _as_text(_get_row_value(row, "summary", "abstract"))
        authors = _as_list(_get_row_value(row, "authors", "authors_joined"))
        categories = _as_list(_get_row_value(row, "categories", "categories_joined"))
        published = _as_text(_get_row_value(row, "published", "publication_date"))

        if not paper_id:
            paper_id = f"paper-{index + 1}"

        if title:
            if summary:
                samples.append(
                    {
                        "id": f"q{len(samples) + 1}",
                        "question_type": "factual",
                        "question": f"Tóm tắt chính của bài viết về '{title}' là gì?",
                        "ground_truth": summary,
                        "ground_truth_doc_ids": [paper_id],
                    }
                )

            if authors:
                samples.append(
                    {
                        "id": f"q{len(samples) + 1}",
                        "question_type": "factual",
                        "question": f"Tác giả của bài viết về '{title}' là ai?",
                        "ground_truth": ", ".join(authors),
                        "ground_truth_doc_ids": [paper_id],
                    }
                )

            if published:
                samples.append(
                    {
                        "id": f"q{len(samples) + 1}",
                        "question_type": "factual",
                        "question": f"Bài viết '{title}' được xuất bản vào ngày nào?",
                        "ground_truth": published,
                        "ground_truth_doc_ids": [paper_id],
                    }
                )

            if categories:
                samples.append(
                    {
                        "id": f"q{len(samples) + 1}",
                        "question_type": "factual",
                        "question": f"Các danh mục chính của bài viết '{title}' là gì?",
                        "ground_truth": ", ".join(categories),
                        "ground_truth_doc_ids": [paper_id],
                    }
                )

    if len(samples) < 5:
        raise ValueError("Unable to create at least 5 evaluation questions from the supplied dataframe")

    output_path = Path(output_path)
    write_json(output_path, samples)
    return samples
