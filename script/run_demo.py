from __future__ import annotations

import argparse
from dataclasses import replace
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.config import load_settings, normalized_provider, require_llm_credentials
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex


SAMPLE_QUESTIONS = [
    "Hãy tìm bài báo 'Reliable retrieval-augmented feature generation with large language model reasoning' và cho biết các tác giả.",
    "Tóm tắt bài báo 'Hallucination in Large Language Models and Retrieval-Augmented Generation: Mechanisms, Mitigation, and Evaluation'.",
    "Trong corpus hiện tại có những bài báo nào liên quan đến retrieval-augmented generation? Hãy nêu DOI và tiêu đề.",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the paper-corpus RAG agent configured in .env.")
    parser.add_argument("-q", "--question", action="append", help="Ask a question; repeat -q for multiple questions.")
    parser.add_argument("--sample", action="store_true", help="Run three prepared demo questions.")
    return parser.parse_args()


def _ask(agent, question: str) -> None:
    print(f"\nYou: {question}")
    try:
        answer = run_agent_question(agent, question)
    except Exception as exc:
        raise RuntimeError(f"The LLM request failed: {exc}") from exc
    print(f"\nAgent: {answer}\n")


def _load_demo_index(settings):
    """Load baseline ChromaDB, rebuilding an isolated demo copy on ACL errors."""
    try:
        return LocalEmbeddingIndex.load(settings, settings.paths.embeddings_json)
    except Exception as exc:
        if "access is denied" not in str(exc).lower():
            raise

        if not settings.paths.clean_csv.exists():
            raise RuntimeError(
                "ChromaDB is not accessible and papers_clean.csv is unavailable for a local rebuild."
            ) from exc

        demo_manifest = settings.paths.project_dir / "data" / "embeddings" / "papers_embeddings_demo.json"
        demo_chroma_dir = settings.paths.project_dir / "data" / "chroma_demo"
        demo_paths = replace(
            settings.paths,
            chroma_dir=demo_chroma_dir,
            embeddings_json=demo_manifest,
        )
        demo_settings = replace(settings, paths=demo_paths, baseline_collection_name="papers-demo")

        # Reuse the isolated collection whenever possible. Rebuilding on every
        # process start deletes/recreates the collection and invalidates handles
        # held by another running CLI or UI process.
        if demo_manifest.exists():
            try:
                print("Using the isolated demo index...")
                return LocalEmbeddingIndex.load(demo_settings, demo_manifest)
            except Exception as demo_exc:
                print(f"The isolated demo index is unavailable ({demo_exc}); rebuilding it...")

        clean_df = pd.read_csv(settings.paths.clean_csv, keep_default_na=False)
        if clean_df.empty:
            raise RuntimeError("papers_clean.csv is empty; the demo index cannot be rebuilt.") from exc

        print("Baseline ChromaDB is not accessible; rebuilding an isolated demo index...")
        return LocalEmbeddingIndex.build(
            clean_df,
            demo_settings,
            embeddings_output_path=demo_manifest,
        )


def main() -> None:
    args = _parse_args()
    settings = load_settings(ROOT)
    provider = normalized_provider(settings)
    try:
        require_llm_credentials(settings)
    except RuntimeError as exc:
        raise SystemExit(f"Invalid .env configuration: {exc}") from exc

    if not settings.paths.embeddings_json.exists():
        raise SystemExit("Baseline index not found. Run: python script/run_phase1.py")

    try:
        index = _load_demo_index(settings)
        agent = build_agent(settings, index)
    except Exception as exc:
        raise SystemExit(f"Could not initialize the demo: {exc}") from exc

    print("=== Paper Corpus RAG Demo ===")
    print(f"Provider   : {provider}")
    print(f"LLM model  : {settings.model_name}")
    print(f"Max tokens : {settings.max_output_tokens}")
    print(f"Collection : {index.collection_name}")
    print(f"Documents  : {len(index.documents)}")

    questions = SAMPLE_QUESTIONS if args.sample else (args.question or [])
    if questions:
        for question in questions:
            _ask(agent, question)
        return

    print("\nNhập câu hỏi về corpus. Gõ exit để thoát.")
    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nĐã kết thúc demo.")
            return
        if question.lower() in {"exit", "quit", "q"}:
            print("Đã kết thúc demo.")
            return
        if question:
            _ask(agent, question)


if __name__ == "__main__":
    main()
