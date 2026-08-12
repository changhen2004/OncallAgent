from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from oncallagent.knowledge.index import KnowledgeIndex

DEFAULT_EVAL_PATH = Path(__file__).resolve().parents[2] / "eval" / "rag_questions.json"


@dataclass(frozen=True)
class EvalQuestion:
    id: str
    question: str
    expected_file: str | None


@dataclass(frozen=True)
class EvalCaseResult:
    id: str
    question: str
    expected_file: str | None
    retrieved_files: list[str]
    hit_rank: int | None

    @property
    def is_negative(self) -> bool:
        return self.expected_file is None

    @property
    def top1_hit(self) -> bool:
        return self.hit_rank == 1

    @property
    def top3_hit(self) -> bool:
        return self.hit_rank is not None and self.hit_rank <= 3


@dataclass(frozen=True)
class EvalReport:
    total: int
    positive_total: int
    top1_hits: int
    top3_hits: int
    mrr: float
    ndcg: float
    ndcg_k: int
    negative_total: int
    negative_false_positives: int
    cases: list[EvalCaseResult]

    @property
    def top1_hit_rate(self) -> float:
        return self.top1_hits / self.positive_total if self.positive_total else 0.0

    @property
    def top3_hit_rate(self) -> float:
        return self.top3_hits / self.positive_total if self.positive_total else 0.0

    @property
    def negative_false_positive_rate(self) -> float:
        return (
            self.negative_false_positives / self.negative_total if self.negative_total else 0.0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "positive_total": self.positive_total,
            "top1_hits": self.top1_hits,
            "top3_hits": self.top3_hits,
            "top1_hit_rate": self.top1_hit_rate,
            "top3_hit_rate": self.top3_hit_rate,
            "mrr": self.mrr,
            "ndcg": self.ndcg,
            "ndcg_k": self.ndcg_k,
            "negative_total": self.negative_total,
            "negative_false_positives": self.negative_false_positives,
            "negative_false_positive_rate": self.negative_false_positive_rate,
            "cases": [asdict(case) for case in self.cases],
        }


def load_eval_questions(
    eval_file: str | Path = DEFAULT_EVAL_PATH, *, docs_dir: str | Path | None = None
) -> list[EvalQuestion]:
    path = Path(eval_file)
    raw_items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_items, list):
        raise ValueError(f"RAG eval file must contain a JSON list: {path}")

    questions: list[EvalQuestion] = []
    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"RAG eval item #{index} must be an object")
        question = EvalQuestion(
            id=_required_string(item, "id", index),
            question=_required_string(item, "question", index),
            expected_file=_optional_string(item, "expected_file", index),
        )
        questions.append(question)

    if docs_dir is not None:
        _validate_expected_files(questions, Path(docs_dir))

    return questions


def evaluate_knowledge_index(
    knowledge: KnowledgeIndex, questions: list[EvalQuestion], *, top_k: int = 3
) -> EvalReport:
    cases = [
        _build_case(
            question,
            [result.filename for result in knowledge.search(question.question, limit=top_k)],
        )
        for question in questions
    ]
    return _build_report(cases, top_k=top_k)


async def evaluate_knowledge_index_hybrid(
    knowledge: KnowledgeIndex, questions: list[EvalQuestion], *, top_k: int = 3
) -> EvalReport:
    cases: list[EvalCaseResult] = []
    for question in questions:
        retrieved_files = [
            result.filename
            for result in await knowledge.search_hybrid(question.question, limit=top_k)
        ]
        cases.append(_build_case(question, retrieved_files))
    return _build_report(cases, top_k=top_k)


def evaluate_default_runbooks(
    *,
    docs_dir: str | Path = "docs/runbooks",
    eval_file: str | Path = DEFAULT_EVAL_PATH,
    top_k: int = 3,
) -> EvalReport:
    docs_path = Path(docs_dir)
    questions = load_eval_questions(eval_file, docs_dir=docs_path)
    return evaluate_knowledge_index(KnowledgeIndex(docs_path), questions, top_k=top_k)


def _build_case(
    question: EvalQuestion, retrieved_files: list[str]
) -> EvalCaseResult:
    if question.expected_file is None:
        return EvalCaseResult(
            id=question.id,
            question=question.question,
            expected_file=None,
            retrieved_files=retrieved_files,
            hit_rank=None,
        )
    return EvalCaseResult(
        id=question.id,
        question=question.question,
        expected_file=question.expected_file,
        retrieved_files=retrieved_files,
        hit_rank=_hit_rank(retrieved_files, question.expected_file),
    )


def _build_report(cases: list[EvalCaseResult], *, top_k: int) -> EvalReport:
    positive = [case for case in cases if not case.is_negative]
    negative = [case for case in cases if case.is_negative]
    mrr = (
        sum(1.0 / case.hit_rank for case in positive if case.hit_rank) / len(positive)
        if positive
        else 0.0
    )
    ndcg = (
        sum(_ndcg_at_k(case.hit_rank, top_k) for case in positive) / len(positive)
        if positive
        else 0.0
    )
    return EvalReport(
        total=len(cases),
        positive_total=len(positive),
        top1_hits=sum(case.top1_hit for case in positive),
        top3_hits=sum(case.top3_hit for case in positive),
        mrr=mrr,
        ndcg=ndcg,
        ndcg_k=top_k,
        negative_total=len(negative),
        negative_false_positives=sum(1 for case in negative if case.retrieved_files),
        cases=cases,
    )


def _ndcg_at_k(hit_rank: int | None, top_k: int) -> float:
    if hit_rank is None or hit_rank > top_k:
        return 0.0
    return 1.0 / math.log2(hit_rank + 1)


def _required_string(item: dict[str, Any], key: str, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"RAG eval item #{index} has invalid {key!r}")
    return value.strip()


def _optional_string(item: dict[str, Any], key: str, index: int) -> str | None:
    value = item.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"RAG eval item #{index} has invalid {key!r}")
    return value.strip()


def _validate_expected_files(questions: list[EvalQuestion], docs_dir: Path) -> None:
    existing_files = {path.name for path in docs_dir.glob("*.md")}
    for question in questions:
        if question.expected_file is None:
            continue
        if question.expected_file not in existing_files:
            raise ValueError(
                f"RAG eval question {question.id!r} references missing file: "
                f"{question.expected_file}"
            )


def _hit_rank(retrieved_files: list[str], expected_file: str) -> int | None:
    try:
        return retrieved_files.index(expected_file) + 1
    except ValueError:
        return None
