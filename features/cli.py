from __future__ import annotations

import argparse
from pathlib import Path

from features.services.demo_data import demo_evidence_for_sample
from features.services.analyzer import CaseAnalyzer


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a KANIT sample analysis.")
    parser.add_argument("--sample", default="01_missing_evidence")
    args = parser.parse_args()

    sample_path = Path("features/data/sample_cases") / f"{args.sample}.txt"
    case_text = sample_path.read_text(encoding="utf-8")
    report = CaseAnalyzer().analyze(case_text, demo_evidence_for_sample(args.sample))
    print(report.markdown_report)


if __name__ == "__main__":
    main()
