import argparse
import sys
from pathlib import Path

src_root = Path(__file__).resolve().parents[1] / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from pipelines.corruption_flow import main
from ingestion.corruption import CorruptionConfig

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Corruption and Repair Flow")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for corruption")
    parser.add_argument("--missing-summary-fraction", type=float, default=0.15)
    parser.add_argument("--stale-date-fraction", type=float, default=0.15)
    parser.add_argument("--noise-fraction", type=float, default=0.10)
    parser.add_argument("--duplicate-fraction", type=float, default=0.10)
    parser.add_argument("--drop-fraction", type=float, default=0.10)

    args = parser.parse_args()
    
    config = CorruptionConfig(
        seed=args.seed,
        missing_summary_fraction=args.missing_summary_fraction,
        stale_date_fraction=args.stale_date_fraction,
        noisy_text_fraction=args.noise_fraction,
        duplicate_fraction=args.duplicate_fraction,
        drop_fraction=args.drop_fraction,
    )

    try:
        main(seed=args.seed, config=config)
    except Exception as e:
        print(f"Pipeline failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
