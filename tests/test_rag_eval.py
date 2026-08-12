from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest


def test_evaluate_knowledge_index_reports_topk_hit_rates(tmp_path: Path) -> None:
    from oncallagent.knowledge.index import KnowledgeIndex
    from oncallagent.eval.rag_eval import EvalQuestion, evaluate_knowledge_index

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
    assert report.positive_total == 3
    assert report.top1_hits == 3
    assert report.top3_hits == 3
    assert report.top1_hit_rate == 1.0
    assert report.top3_hit_rate == 1.0
    assert report.mrr == 1.0
    assert report.ndcg == 1.0
    assert report.negative_total == 0
    assert report.negative_false_positives == 0
    assert [case.hit_rank for case in report.cases] == [1, 1, 1]


def test_evaluate_knowledge_index_computes_mrr_and_ndcg(tmp_path: Path) -> None:
    from oncallagent.knowledge.index import KnowledgeIndex
    from oncallagent.eval.rag_eval import EvalQuestion, evaluate_knowledge_index

    (tmp_path / "latency.md").write_text("latency redis cache", encoding="utf-8")
    (tmp_path / "error.md").write_text("latency 5xx error rate", encoding="utf-8")

    questions = [
        EvalQuestion(
            id="q1",
            question="latency redis",
            expected_file="error.md",
        )
    ]

    report = evaluate_knowledge_index(KnowledgeIndex(tmp_path), questions, top_k=3)

    assert report.cases[0].hit_rank == 2
    assert report.mrr == pytest.approx(0.5)
    assert report.ndcg == pytest.approx(1.0 / math.log2(3))


def test_evaluate_knowledge_index_reports_negative_false_positives(tmp_path: Path) -> None:
    from oncallagent.knowledge.index import KnowledgeIndex
    from oncallagent.eval.rag_eval import EvalQuestion, evaluate_knowledge_index

    (tmp_path / "latency.md").write_text("P95 latency Redis cache slow route", encoding="utf-8")

    questions = [
        EvalQuestion(
            id="q1",
            question="P95 latency is high and Redis cache may be unavailable",
            expected_file="latency.md",
        ),
        EvalQuestion(id="neg-1", question="今天上海天气怎么样", expected_file=None),
        EvalQuestion(id="neg-2", question="Kubernetes 集群节点如何扩容", expected_file=None),
    ]

    report = evaluate_knowledge_index(KnowledgeIndex(tmp_path), questions, top_k=3)

    assert report.total == 3
    assert report.positive_total == 1
    assert report.negative_total == 2
    assert report.negative_false_positives == 0
    assert report.top1_hit_rate == 1.0
    assert [case.hit_rank for case in report.cases] == [1, None, None]
    assert report.cases[0].retrieved_files == ["latency.md"]
    assert report.cases[1].retrieved_files == []


def test_evaluate_knowledge_index_counts_negative_false_recall(tmp_path: Path) -> None:
    from oncallagent.knowledge.index import KnowledgeIndex
    from oncallagent.eval.rag_eval import EvalQuestion, evaluate_knowledge_index

    (tmp_path / "latency.md").write_text("Grafana 告警面板 Redis 缓存", encoding="utf-8")

    questions = [
        EvalQuestion(
            id="neg-1",
            question="如何配置 Grafana 的告警通知渠道",
            expected_file=None,
        )
    ]

    report = evaluate_knowledge_index(KnowledgeIndex(tmp_path), questions, top_k=3)

    assert report.negative_total == 1
    assert report.negative_false_positives == 1
    assert report.negative_false_positive_rate == 1.0


def test_load_eval_questions_accepts_null_expected_file_for_negative_cases(
    tmp_path: Path,
) -> None:
    from oncallagent.eval.rag_eval import load_eval_questions

    eval_file = tmp_path / "questions.json"
    eval_file.write_text(
        json.dumps(
            [
                {
                    "id": "neg-1",
                    "question": "unrelated question",
                    "expected_file": None,
                }
            ]
        ),
        encoding="utf-8",
    )

    questions = load_eval_questions(eval_file, docs_dir=tmp_path)

    assert questions[0].expected_file is None


def test_load_eval_questions_rejects_invalid_expected_file(tmp_path: Path) -> None:
    from oncallagent.eval.rag_eval import load_eval_questions

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
    from oncallagent.eval.rag_eval import DEFAULT_EVAL_PATH, load_eval_questions

    docs_dir = Path("docs/runbooks")

    questions = load_eval_questions(DEFAULT_EVAL_PATH, docs_dir=docs_dir)

    assert len(questions) >= 30
    expected_files = {question.expected_file for question in questions if question.expected_file}
    actual_files = {path.name for path in docs_dir.glob("*.md")}
    assert expected_files <= actual_files
    assert any(question.expected_file is None for question in questions)


def test_rag_eval_script_runs_from_repo_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/rag_eval.py", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )

    report = json.loads(result.stdout)
    assert report["total"] >= 30
    assert report["positive_total"] >= 30
    assert report["top3_hits"] == report["positive_total"]
    assert report["mrr"] > 0.98
    assert report["ndcg"] > 0.98
    assert report["negative_total"] >= 1
    assert "negative_false_positives" in report


def test_default_rag_eval_keeps_high_top1_and_full_top3() -> None:
    from oncallagent.eval.rag_eval import evaluate_default_runbooks

    report = evaluate_default_runbooks()
    non_top1_positive_cases = [
        case.id for case in report.cases if not case.is_negative and case.hit_rank != 1
    ]

    assert report.top1_hits >= 35
    assert report.top3_hits == report.positive_total
    assert report.mrr > 0.98
    assert report.negative_total >= 1
    assert len(non_top1_positive_cases) <= 2


@pytest.mark.anyio
async def test_evaluate_knowledge_index_hybrid_uses_vector_results(tmp_path: Path) -> None:
    from oncallagent.eval.rag_eval import EvalQuestion, evaluate_knowledge_index_hybrid
    from oncallagent.knowledge.index import KnowledgeIndex

    (tmp_path / "error.md").write_text("5xx error rate high", encoding="utf-8")

    class FakeVectorStore:
        async def search(
            self,
            query: str,
            *,
            limit: int = 3,
            score_threshold: float = 0.5,
            payload_filter: dict | None = None,
        ):
            return [{"source": "error.md", "content": "5xx steps", "score": 0.9}]

    questions = [
        EvalQuestion(
            id="q1",
            question="错误率升高的时候应该参考哪份手册",
            expected_file="error.md",
        )
    ]
    knowledge = KnowledgeIndex(tmp_path, vector_store=FakeVectorStore())

    report = await evaluate_knowledge_index_hybrid(knowledge, questions, top_k=3)

    assert report.top1_hits == 1
    assert report.cases[0].hit_rank == 1


@pytest.mark.anyio
async def test_evaluate_knowledge_index_hybrid_counts_negative_cases(tmp_path: Path) -> None:
    from oncallagent.eval.rag_eval import EvalQuestion, evaluate_knowledge_index_hybrid
    from oncallagent.knowledge.index import KnowledgeIndex

    (tmp_path / "error.md").write_text("5xx error rate high", encoding="utf-8")

    class EmptyVectorStore:
        async def search(
            self,
            query: str,
            *,
            limit: int = 3,
            score_threshold: float = 0.5,
            payload_filter: dict | None = None,
        ):
            return []

    questions = [
        EvalQuestion(id="neg-1", question="今天上海天气怎么样", expected_file=None),
    ]
    knowledge = KnowledgeIndex(tmp_path, vector_store=EmptyVectorStore())

    report = await evaluate_knowledge_index_hybrid(knowledge, questions, top_k=3)

    assert report.negative_total == 1
    assert report.negative_false_positives == 0
