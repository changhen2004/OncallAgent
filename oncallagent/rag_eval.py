from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from oncallagent.knowledge import KnowledgeIndex

DEFAULT_EVAL_PATH = Path(__file__).resolve().parents[1] / "eval" / "rag_questions.json"


@dataclass(frozen=True)
class EvalQuestion:
    id: str
    question: str
    expected_file: str


@dataclass(frozen=True)
class EvalCaseResult:
    id: str
    question: str
    expected_file: str
    retrieved_files: list[str]
    hit_rank: int | None

    @property
    def top1_hit(self) -> bool:
        return self.hit_rank == 1

    @property
    def top3_hit(self) -> bool:
        return self.hit_rank is not None and self.hit_rank <= 3


@dataclass(frozen=True)
class EvalReport:
    total: int
    top1_hits: int
    top3_hits: int
    cases: list[EvalCaseResult]

    @property
    def top1_hit_rate(self) -> float:
        return self.top1_hits / self.total if self.total else 0.0

    @property
    def top3_hit_rate(self) -> float:
        return self.top3_hits / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "top1_hits": self.top1_hits,
            "top3_hits": self.top3_hits,
            "top1_hit_rate": self.top1_hit_rate,
            "top3_hit_rate": self.top3_hit_rate,
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
            expected_file=_required_string(item, "expected_file", index),
        )
        questions.append(question)

    if docs_dir is not None:
        _validate_expected_files(questions, Path(docs_dir))

    return questions


def evaluate_knowledge_index(
    knowledge: KnowledgeIndex, questions: list[EvalQuestion], *, top_k: int = 3
) -> EvalReport:
    cases: list[EvalCaseResult] = []
    for question in questions:
        retrieved_files = [
            result.filename for result in knowledge.search(question.question, limit=top_k)
        ]
        hit_rank = _hit_rank(retrieved_files, question.expected_file)
        cases.append(
            EvalCaseResult(
                id=question.id,
                question=question.question,
                expected_file=question.expected_file,
                retrieved_files=retrieved_files,
                hit_rank=hit_rank,
            )
        )

    return EvalReport(
        total=len(cases),
        top1_hits=sum(case.top1_hit for case in cases),
        top3_hits=sum(case.top3_hit for case in cases),
        cases=cases,
    )


def evaluate_default_runbooks(
    *,
    docs_dir: str | Path = "docs/runbooks",
    eval_file: str | Path = DEFAULT_EVAL_PATH,
    top_k: int = 3,
) -> EvalReport:
    docs_path = Path(docs_dir)
    questions = load_eval_questions(eval_file, docs_dir=docs_path)
    return evaluate_knowledge_index(KnowledgeIndex(docs_path), questions, top_k=top_k)


def _required_string(item: dict[str, Any], key: str, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"RAG eval item #{index} has invalid {key!r}")
    return value.strip()


def _validate_expected_files(questions: list[EvalQuestion], docs_dir: Path) -> None:
    existing_files = {path.name for path in docs_dir.glob("*.md")}
    for question in questions:
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
