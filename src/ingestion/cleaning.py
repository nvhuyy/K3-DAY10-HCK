from __future__ import annotations

from datetime import datetime

import pandas as pd

from ingestion.crossref import PaperRecord


def _normalize_list(items: list[str] | None) -> list[str]:
    if not items:
        return []
    normalized: list[str] = []
    for item in items:
        if item is None:
            continue
        value = str(item).strip()
        if value:
            normalized.append(value)
    return normalized


def _normalize_text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_date(value: object | None) -> str:
    if value is None:
        return ""
    date = pd.to_datetime(str(value), errors="coerce", utc=False)
    if pd.isna(date):
        return ""
    return date.strftime("%Y-%m-%d")


def _build_text_for_embedding(row: pd.Series) -> str:
    parts = [row["title"], row["summary"], row["authors_joined"], row["categories_joined"]]
    return " \n\n".join([part for part in parts if isinstance(part, str) and part]).strip()


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw PaperRecord objects into a dataframe ready for embedding."""
    if not records:
        return pd.DataFrame()

    raw_data = []
    for record in records:
        raw_data.append(
            {
                "paper_id": _normalize_text(record.paper_id),
                "title": _normalize_text(record.title),
                "summary": _normalize_text(record.summary),
                "authors": _normalize_list(record.authors),
                "categories": _normalize_list(record.categories),
                "primary_category": _normalize_text(record.primary_category),
                "published": _parse_date(record.published),
                "updated": _parse_date(record.updated),
                "abs_url": _normalize_text(record.abs_url),
                "pdf_url": _normalize_text(record.pdf_url),
                "comment": _normalize_text(record.comment),
            }
        )

    df = pd.DataFrame(raw_data)
    if df.empty:
        return df

    df["published"] = df["published"].fillna("")
    df["updated"] = df["updated"].fillna("")

    # Prefer published date for freshness and fallback to updated date if published is missing.
    published_datetime = pd.to_datetime(df["published"], errors="coerce", utc=False)
    updated_datetime = pd.to_datetime(df["updated"], errors="coerce", utc=False)
    df["effective_date"] = published_datetime.fillna(updated_datetime)
    df["published"] = df["effective_date"].dt.strftime("%Y-%m-%d").fillna("")
    df["updated"] = updated_datetime.dt.strftime("%Y-%m-%d").fillna("")

    df["age_days"] = (pd.to_datetime(run_date) - df["effective_date"]).dt.days
    df["age_days"] = df["age_days"].fillna(-1).astype(int)
    df.loc[df["age_days"] < 0, "age_days"] = 0

    df["authors_joined"] = df["authors"].apply(lambda values: ", ".join(values) if isinstance(values, list) else "")
    df["categories_joined"] = df["categories"].apply(lambda values: ", ".join(values) if isinstance(values, list) else "")
    df["summary_chars"] = df["summary"].astype(str).apply(len)
    df["text_for_embedding"] = df.apply(_build_text_for_embedding, axis=1)

    # Remove invalid or unhelpful rows.
    df = df[df["paper_id"].astype(bool)]
    df = df[df["title"].astype(bool)]
    df = df[df["summary_chars"] >= 20]
    df = df[df["text_for_embedding"].astype(bool)]

    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    df = df.sort_values(by=["effective_date", "paper_id"], ascending=[False, True])

    df = df.drop(columns=["effective_date"])
    df = df.reset_index(drop=True)
    return df
