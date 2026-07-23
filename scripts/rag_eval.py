from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from oncallagent.rag_eval import DEFAULT_EVAL_PATH, EvalReport, evaluate_default_runbooks


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate OnCallAgent runbook RAG hits.")
    parser.add_argument("--docs-dir", default="docs/runbooks")
    parser.add_argument("--eval-file", default=str(DEFAULT_EVAL_PATH))
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    report = evaluate_default_runbooks(
        docs_dir=Path(args.docs_dir),
        eval_file=Path(args.eval_file),
        top_k=args.top_k,
    )
    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return
    print(_format_markdown(report))


def _format_markdown(report: EvalReport) -> str:
    lines = [
        "# RAG Eval Report",
        "",
        f"- Total questions: {report.total}",
        f"- Top1 hits: {report.top1_hits}/{report.total} ({report.top1_hit_rate:.2%})",
        f"- Top3 hits: {report.top3_hits}/{report.total} ({report.top3_hit_rate:.2%})",
        "",
        "| ID | Expected | Hit Rank | Retrieved |",
        "|----|----------|----------|-----------|",
    ]
    for case in report.cases:
        rank = str(case.hit_rank) if case.hit_rank is not None else "miss"
        retrieved = ", ".join(case.retrieved_files) if case.retrieved_files else "-"
        lines.append(
            f"| {case.id} | {case.expected_file} | {rank} | {retrieved} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
