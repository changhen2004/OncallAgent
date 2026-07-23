from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fastapi import UploadFile


_TOKEN_RE = re.compile(r"[A-Za-z0-9_.-]+|[\u4e00-\u9fff]+")


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
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        results: list[SearchResult] = []
        for filename, content in self._documents.items():
            doc_tokens = set(_tokenize(filename)) | set(_tokenize(content))
            score = len(set(query_tokens) & doc_tokens)
            score += _metadata_match_bonus(query_tokens, filename, content)
            score += _phrase_match_bonus(query, content)
            if score > 0:
                results.append(SearchResult(filename=filename, content=content, score=score))

        return sorted(results, key=lambda item: (-item.score, item.filename))[:limit]

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = Path(filename).name.strip() or "upload.md"
        return re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]", "_", name)


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0).lower()
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            tokens.extend(_chinese_ngrams(token))
        else:
            tokens.append(token)
    return tokens


def _chinese_ngrams(text: str) -> list[str]:
    if len(text) <= 1:
        return [text]
    grams: list[str] = []
    for size in (2, 3):
        if len(text) >= size:
            grams.extend(text[index : index + size] for index in range(len(text) - size + 1))
    return grams


def _metadata_match_bonus(query_tokens: list[str], filename: str, content: str) -> int:
    query_set = set(query_tokens)
    metadata_tokens = set(_tokenize(filename))
    for heading in re.findall(r"(?m)^#{1,3}\s+(.+)$", content):
        metadata_tokens.update(_tokenize(heading))
    return len(query_set & metadata_tokens) * 3


def _phrase_match_bonus(query: str, content: str) -> int:
    query_words = re.findall(r"[A-Za-z0-9_.-]+", query.lower())
    if len(query_words) < 3:
        return 0
    normalized_content = _normalize_phrase_text(content)
    bonus = 0
    seen_phrases: set[str] = set()
    for size in range(3, min(5, len(query_words)) + 1):
        for index in range(len(query_words) - size + 1):
            phrase = " ".join(query_words[index : index + size])
            if phrase in seen_phrases:
                continue
            seen_phrases.add(phrase)
            if phrase in normalized_content:
                bonus += size * 2
    return bonus


def _normalize_phrase_text(text: str) -> str:
    return " ".join(re.findall(r"[A-Za-z0-9_.-]+", text.lower()))
