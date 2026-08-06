from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.config import Settings


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_title(item: dict) -> str:
    title_value = item.get("title")
    if isinstance(title_value, list):
        return _normalize_text(title_value[0] if title_value else "")
    if isinstance(title_value, str):
        return _normalize_text(title_value)
    return ""


def _extract_summary(item: dict) -> str:
    abstract = item.get("abstract")
    if isinstance(abstract, str):
        return _normalize_text(abstract)
    return ""


def _extract_authors(item: dict) -> list[str]:
    authors: list[str] = []
    for author in item.get("author") or []:
        if not isinstance(author, dict):
            continue
        name = _normalize_text(author.get("name"))
        if name:
            authors.append(name)
            continue
        family = _normalize_text(author.get("family"))
        given = _normalize_text(author.get("given"))
        if family and given:
            authors.append(f"{given} {family}")
        elif family:
            authors.append(family)
        elif given:
            authors.append(given)
    return authors


def _extract_categories(item: dict) -> list[str]:
    subjects = item.get("subject") or []
    if isinstance(subjects, str):
        subjects = [subjects]
    categories = [_normalize_text(subject) for subject in subjects if _normalize_text(subject)]
    return categories


def _extract_date(item: dict, key: str) -> str:
    container = item.get(key)
    if not isinstance(container, dict):
        return ""
    date_parts = container.get("date-parts")
    if isinstance(date_parts, list) and date_parts:
        first_part = date_parts[0]
        if isinstance(first_part, list):
            parts = [str(part) for part in first_part if part is not None]
            if parts:
                return "-".join(parts)
    date_time = container.get("date-time")
    if isinstance(date_time, str) and date_time:
        return date_time[:10]
    return ""


def _extract_published(item: dict) -> str:
    for key in ("published-print", "published-online", "published", "created", "deposited"):
        date_value = _extract_date(item, key)
        if date_value:
            return date_value
    return ""


def _extract_updated(item: dict) -> str:
    for key in ("deposited", "created"):
        date_value = _extract_date(item, key)
        if date_value:
            return date_value
    return _extract_published(item)


def _extract_abs_url(item: dict, doi: str) -> str:
    url = _normalize_text(item.get("URL"))
    if url:
        return url
    if doi:
        return f"https://doi.org/{doi}"
    return ""


def _extract_pdf_url(item: dict) -> str:
    for link in item.get("link") or []:
        if not isinstance(link, dict):
            continue
        href = _normalize_text(link.get("URL"))
        if not href:
            continue
        content_type = _normalize_text(link.get("content-type")).lower()
        relation = _normalize_text(link.get("relation")).lower()
        if content_type == "application/pdf" or "pdf" in relation or "application/pdf" in content_type:
            return href
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload into a list of PaperRecord objects."""
    message = payload.get("message") if isinstance(payload, dict) else None
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list):
        return []

    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        doi = _normalize_text(item.get("DOI"))
        title = _extract_title(item)
        summary = _extract_summary(item)
        if not doi or not title:
            continue

        categories = _extract_categories(item)
        primary_category = categories[0] if categories else ""
        authors = _extract_authors(item)
        published = _extract_published(item)
        updated = _extract_updated(item)
        abs_url = _extract_abs_url(item, doi)
        pdf_url = _extract_pdf_url(item)
        comment = _normalize_text(item.get("note"))

        if not summary:
            summary = ""

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch source data from Crossref, save raw response and parsed records."""
    params = {
        "query.title": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }

    last_error: Exception | None = None
    payload: dict | None = None
    for attempt in range(1, 5):
        try:
            url = f"https://api.crossref.org/works?{urlencode(params)}"
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
                payload = json.loads(body)
            break
        except HTTPError as exc:
            last_error = exc
            if exc.code in {429, 503} and attempt < 4:
                sleep(2 * attempt)
                continue
            raise RuntimeError(f"Failed to fetch Crossref records: {exc}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:  # pragma: no cover - network path
            last_error = exc
            if attempt >= 4:
                raise RuntimeError(f"Failed to fetch Crossref records: {exc}") from exc
            sleep(2 * attempt)
    else:
        if last_error is not None:
            raise RuntimeError(f"Failed to fetch Crossref records: {last_error}") from last_error

    if payload is None:
        raise RuntimeError("No payload returned from Crossref API.")

    settings.paths.raw_api_response.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.raw_records_json.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.raw_api_response.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    records = parse_crossref_payload(payload)
    settings.paths.raw_records_json.write_text(
        json.dumps([record.__dict__ for record in records], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load a saved JSON snapshot and map it to PaperRecord objects."""
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        if isinstance(payload.get("message"), dict):
            return parse_crossref_payload(payload)
        raise ValueError("Unsupported raw record payload format.")

    if isinstance(payload, list):
        records: list[PaperRecord] = []
        for item in payload:
            if isinstance(item, dict):
                records.append(
                    PaperRecord(
                        paper_id=_normalize_text(item.get("paper_id")),
                        title=_normalize_text(item.get("title")),
                        summary=_normalize_text(item.get("summary")),
                        authors=list(item.get("authors") or []),
                        categories=list(item.get("categories") or []),
                        primary_category=_normalize_text(item.get("primary_category")),
                        published=_normalize_text(item.get("published")),
                        updated=_normalize_text(item.get("updated")),
                        abs_url=_normalize_text(item.get("abs_url")),
                        pdf_url=_normalize_text(item.get("pdf_url")),
                        comment=_normalize_text(item.get("comment")),
                    )
                )
        return records

    raise ValueError("Unsupported raw record payload format.")
