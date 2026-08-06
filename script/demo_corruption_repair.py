import random
import sys
from pathlib import Path

src_root = Path(__file__).resolve().parents[1] / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from core.config import load_settings
from core.utils import read_json


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60 + "\n")


def print_metric(name: str, baseline: float, corrupted: float, repaired: float):
    print(f"{name:<20} | {baseline:>8.3f} | {corrupted:>9.3f} | {repaired:>8.3f}")


def main() -> None:
    if sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass

    settings = load_settings()
    
    comp_path = settings.paths.quality_dir.parent / "comparison.json"
    if not comp_path.exists():
        print(f"Comparison report not found at {comp_path}. Please run run_corruption_flow.py first.")
        sys.exit(1)
        
    comp = read_json(comp_path)
    b_metrics = comp.get("baseline", {})
    c_metrics = comp.get("corrupted", {})
    r_metrics = comp.get("repaired", {})
    recovery = comp.get("recovery", {})
    
    print_section("RAG METRICS COMPARISON")
    print(f"{'Metric':<20} | Baseline | Corrupted | Repaired")
    print("-" * 55)
    print_metric("Hit Rate", b_metrics.get("retrieval_hit_rate", 0), c_metrics.get("retrieval_hit_rate", 0), r_metrics.get("retrieval_hit_rate", 0))
    print_metric("Token F1", b_metrics.get("mean_token_f1", 0), c_metrics.get("mean_token_f1", 0), r_metrics.get("mean_token_f1", 0))
    print_metric("Judge Accuracy", b_metrics.get("judge_accuracy", 0), c_metrics.get("judge_accuracy", 0), r_metrics.get("judge_accuracy", 0))
    print_metric("Judge Score", b_metrics.get("mean_judge_score", 0), c_metrics.get("mean_judge_score", 0), r_metrics.get("mean_judge_score", 0))
    
    print("\nRecovery:")
    print(f"  Hit Rate Recovery: {recovery.get('retrieval_hit_rate', 0):.2%}")
    print(f"  Token F1 Recovery: {recovery.get('mean_token_f1', 0):.2%}")
    
    print_section("RAG ANSWERS DEMO")
    try:
        b_ans = read_json(settings.paths.baseline_answers)
        c_ans = read_json(settings.paths.corrupted_answers)
        r_ans = read_json(settings.paths.repaired_answers)
        
        if not b_ans:
            print("No answers available to demo.")
            return
            
        # Pick a random question
        idx = random.randint(0, len(b_ans) - 1)
        
        # Sometimes test set might be shuffled, better match by ID
        target_id = b_ans[idx]["id"]
        
        def find_ans(answers, q_id):
            for a in answers:
                if a["id"] == q_id:
                    return a
            return None
            
        b_item = find_ans(b_ans, target_id)
        c_item = find_ans(c_ans, target_id)
        r_item = find_ans(r_ans, target_id)
        
        if not b_item or not c_item or not r_item:
            print("Could not match question ID across all answer files.")
            return
            
        print(f"Question ID: {target_id}")
        print(f"Q: {b_item['question']}\n")
        
        print(f"[BASELINE] (Hit: {b_item['retrieval_hit']})")
        print(b_item['answer'])
        print("-" * 60)
        
        print(f"[CORRUPTED] (Hit: {c_item['retrieval_hit']})")
        print(c_item['answer'])
        print("-" * 60)
        
        print(f"[REPAIRED] (Hit: {r_item['retrieval_hit']})")
        print(r_item['answer'])
        
    except FileNotFoundError:
        print("Answer JSON files not found. Did you run the pipeline?")


if __name__ == "__main__":
    main()
