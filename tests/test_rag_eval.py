from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_evaluate_knowledge_index_reports_topk_hit_rates(tmp_path: Path) -> None:
    from oncallagent.knowledge import KnowledgeIndex
    from oncallagent.rag_eval import EvalQuestion, evaluate_knowledge_index

    (tmp_path / "latency.md").write_text("P95 latency Redis cache slow route", encoding="utf-8")
    (tmp_path / "error.md").write_text("5xx error rate MySQL Redis RabbitMQ", encoding="utf-8")
    (tmp_path / "queue.md").write_text("RabbitMQ backlog worker ready unacked", encoding="utf-8")

    questions = [
        EvalQuestion(
            id="q1",
            question="P95 latency is high and Redis cache may be unavailable",
            expected_file="latency.md",
        ),
        EvalQuestion(
            id="q2",
            question="5xx error rate increases on write APIs",
            expected_file="error.md",
        ),
        EvalQuestion(
            id="q3",
            question="RabbitMQ queue backlog ready messages keep increasing",
            expected_file="queue.md",
        ),
    ]

    report = evaluate_knowledge_index(KnowledgeIndex(tmp_path), questions, top_k=3)

    assert report.total == 3
    assert report.top1_hits == 3
    assert report.top3_hits == 3
    assert report.top1_hit_rate == 1.0
    assert report.top3_hit_rate == 1.0
    assert [case.hit_rank for case in report.cases] == [1, 1, 1]


def test_load_eval_questions_rejects_invalid_expected_file(tmp_path: Path) -> None:
    from oncallagent.rag_eval import load_eval_questions

    eval_file = tmp_path / "questions.json"
    eval_file.write_text(
        json.dumps(
            [
                {
                    "id": "bad",
                    "question": "missing target",
                    "expected_file": "missing.md",
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing.md"):
        load_eval_questions(eval_file, docs_dir=tmp_path)


def test_default_rag_eval_dataset_covers_existing_runbooks() -> None:
    from oncallagent.rag_eval import DEFAULT_EVAL_PATH, load_eval_questions

    docs_dir = Path("docs/runbooks")

    questions = load_eval_questions(DEFAULT_EVAL_PATH, docs_dir=docs_dir)

    assert len(questions) >= 30
    expected_files = {question.expected_file for question in questions}
    actual_files = {path.name for path in docs_dir.glob("*.md")}
    assert expected_files <= actual_files


def test_rag_eval_script_runs_from_repo_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/rag_eval.py", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )

    report = json.loads(result.stdout)
    assert report["total"] >= 30
    assert report["top3_hits"] == report["total"]


def test_default_rag_eval_reaches_full_top1_after_failure_sample_optimization() -> None:
    from oncallagent.rag_eval import evaluate_default_runbooks

    report = evaluate_default_runbooks()
    non_top1_cases = [case.id for case in report.cases if case.hit_rank != 1]

    assert report.top1_hits == report.total
    assert non_top1_cases == []
