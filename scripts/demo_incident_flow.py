from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from oncallagent.demo_flow import build_demo_flow_report, dumps_demo_flow_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an offline Prometheus -> Runbook -> Agent demo flow."
    )
    parser.add_argument("--docs-dir", default="docs/runbooks")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    report = build_demo_flow_report(docs_dir=args.docs_dir)
    if args.format == "json":
        print(dumps_demo_flow_json(report))
        return
    print(report.to_markdown())


if __name__ == "__main__":
    main()
