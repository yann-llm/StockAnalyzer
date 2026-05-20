"""Clean persisted Eastmoney industry raw module files for one stock code."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from industry import clean_industry_raw_files
else:
    from . import clean_industry_raw_files


def parse_args() -> argparse.Namespace:
    project_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Clean persisted Eastmoney industry raw files.")
    parser.add_argument("stock_code", help="Stock code used in raw file names, for example 000157.")
    parser.add_argument(
        "--data-dir",
        default=str(project_dir / "data" / "industry"),
        help="Directory containing industry_*_raw_{stock_code}.json files.",
    )
    parser.add_argument("--output", help="Output JSON path. Defaults to data-dir/industry_cleaned_{stock_code}.json.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    output_path = Path(args.output) if args.output else data_dir / f"industry_cleaned_{args.stock_code}.json"
    cleaned = clean_industry_raw_files(args.stock_code, data_dir, output_path)
    score = cleaned["score_summary"]
    print(f"[完成] 行业清洗数据已保存到 {output_path}")
    print(f"[评分] {cleaned['industry_name']} overall={score['overall_score']} rating={score['rating']}")


if __name__ == "__main__":
    main()
