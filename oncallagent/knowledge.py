from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fastapi import UploadFile


_TOKEN_RE = re.compile(r"[A-Za-z0-9_.-]+|[\u4e00-\u9fff]")


@dataclass(frozen=True)
class SearchResult:
    filename: str
    content: str
    score: int


class ExternalIndexer(Protocol):
    async def index_markdown(self, markdown: str) -> None:
        pass


class KnowledgeIndex:
    def __init__(
        self, docs_dir: str | Path = "docs", external_indexer: ExternalIndexer | None = None
    ) -> None:
        self.docs_dir = Path(docs_dir)
        self.external_indexer = external_indexer
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self._documents: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        self._documents.clear()
        for path in sorted(self.docs_dir.glob("*.md")):
            self._documents[path.name] = path.read_text(encoding="utf-8")

    async def save_upload(self, file: UploadFile) -> str:
        filename = self._safe_filename(file.filename or "upload.md")
        target = self.docs_dir / filename
        content = await file.read()
        target.write_bytes(content)
        markdown = content.decode("utf-8", errors="ignore")
        if self.external_indexer is not None:
            await self.external_indexer.index_markdown(markdown)
        self._documents[filename] = markdown
        return "上传成功"

    def search(self, query: str, limit: int = 3) -> list[SearchResult]:
        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return []

        results: list[SearchResult] = []
        for filename, content in self._documents.items():
            doc_tokens = set(_tokenize(filename)) | set(_tokenize(content))
            score = len(query_tokens & doc_tokens)
            if score > 0:
                results.append(SearchResult(filename=filename, content=content, score=score))

        return sorted(results, key=lambda item: item.score, reverse=True)[:limit]

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = Path(filename).name.strip() or "upload.md"
        return re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]", "_", name)


def _tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(text)]
