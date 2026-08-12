from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4

from oncallagent.knowledge.embedding import average_embeddings, normalize_embedding


class EmbeddingService(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        pass


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    content: str
    heading: str = ""


@dataclass(frozen=True)
class VectorPoint:
    id: str
    vector: list[float]
    payload: dict[str, object]


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_ALERTNAME_RE = re.compile(r"告警名[：:]\s*`([^`]+)`")
_METRIC_LINE_RE = re.compile(r"(?:重点指标|指标)[：:]\s*([^\n]+)")
_BACKTICK_RE = re.compile(r"`([^`]+)`")


def split_markdown(
    markdown: str,
    *,
    max_chunk_chars: int = 1500,
    overlap_chars: int = 100,
) -> list[DocumentChunk]:
    """Split markdown into hierarchical chunks by heading level.

    Each chunk keeps its ancestor headings as context and records the heading
    path (e.g. ``Manual > Steps``).  Bodies longer than ``max_chunk_chars`` are
    split into overlapping pieces so retrieval stays precise without losing
    context across boundaries.
    """
    root, preamble = _parse_sections(markdown)
    chunks: list[DocumentChunk] = []
    if preamble:
        _append_chunk(chunks, "\n".join(preamble), heading="")
    for section in root:
        _emit_section_chunks(
            section, (), chunks, max_chunk_chars=max_chunk_chars, overlap_chars=overlap_chars
        )
    return chunks


def split_markdown_by_h1(markdown: str) -> list[DocumentChunk]:
    return split_markdown(markdown, max_chunk_chars=1_000_000, overlap_chars=0)


def split_text_into_pieces(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    """Split ``text`` at line boundaries, repeating a tail for overlap."""
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    current: list[str] = []
    for line in text.split("\n"):
        if len(line) > max_chars:
            if current:
                pieces.append("\n".join(current))
                current = _overlap_tail(current, overlap_chars)
            for start in range(0, len(line), max_chars - overlap_chars):
                pieces.append(line[start : start + max_chars])
            current = []
            continue
        if current and _joined_len(current) + len(line) + 1 > max_chars:
            pieces.append("\n".join(current))
            current = _overlap_tail(current, overlap_chars)
        current.append(line)
    if current:
        pieces.append("\n".join(current))
    return pieces


async def build_vector_points(
    chunks: list[DocumentChunk], embedder: EmbeddingService
) -> list[VectorPoint]:
    points: list[VectorPoint] = []
    passage_prefix = getattr(embedder, "passage_prefix", "") or ""
    for chunk in chunks:
        if chunk.heading:
            heading_parts = [part.strip() for part in chunk.heading.split(" > ")]
            body_lines = chunk.content.split("\n")[len(heading_parts) :]
        else:
            lines = chunk.content.split("\n")
            if not lines or not lines[0].startswith("#"):
                continue
            heading_parts = [lines[0].lstrip("#").strip()]
            body_lines = lines[1:]

        title = heading_parts[-1]
        weighted_text = [title, title, *heading_parts[:-1], *body_lines]
        if passage_prefix:
            weighted_text = [f"{passage_prefix} {text}" for text in weighted_text]
        embeddings = await embedder.embed(weighted_text)
        vector = normalize_embedding(average_embeddings(embeddings))

        payload: dict[str, object] = {"content": chunk.content}
        if chunk.heading:
            payload["heading"] = chunk.heading
        points.append(VectorPoint(id=chunk.id, vector=vector, payload=payload))
    return points


def extract_runbook_metadata(markdown: str) -> dict[str, object]:
    """Extract alert name and metric names from a runbook's 适用告警 section."""
    alertnames = [match.group(1).strip() for match in _ALERTNAME_RE.finditer(markdown)]
    metrics: list[str] = []
    for line in _METRIC_LINE_RE.finditer(markdown):
        for name in _BACKTICK_RE.findall(line.group(1)):
            name = name.strip()
            if name:
                metrics.append(name)
    return {
        "alertname": alertnames[0] if alertnames else "",
        "metrics": metrics,
    }


@dataclass
class _Section:
    level: int
    heading: str
    body: list[str] = field(default_factory=list)
    children: list["_Section"] = field(default_factory=list)


def _parse_sections(markdown: str) -> tuple[list[_Section], list[str]]:
    root: list[_Section] = []
    stack: list[_Section] = []
    preamble: list[str] = []
    pending: list[str] = []
    in_code = False

    def flush_pending() -> None:
        nonlocal pending
        if not pending:
            return
        if stack:
            stack[-1].body.extend(pending)
        else:
            preamble.extend(pending)
        pending = []

    for raw_line in markdown.splitlines():
        if _FENCE_RE.match(raw_line):
            in_code = not in_code
            pending.append(raw_line)
            continue
        match = _HEADING_RE.match(raw_line) if not in_code else None
        if match is None:
            pending.append(raw_line)
            continue
        flush_pending()
        level = len(match.group(1))
        section = _Section(level=level, heading=match.group(2).strip())
        while stack and stack[-1].level >= level:
            stack.pop()
        if stack:
            stack[-1].children.append(section)
        else:
            root.append(section)
        stack.append(section)

    flush_pending()
    return root, preamble


def _emit_section_chunks(
    section: _Section,
    ancestors: tuple[str, ...],
    chunks: list[DocumentChunk],
    *,
    max_chunk_chars: int,
    overlap_chars: int,
) -> None:
    heading_path = (*ancestors, section.heading)
    prefix = "\n".join(
        f"{'#' * level} {name}" for level, name in enumerate(heading_path, start=1)
    )
    if section.body:
        body = "\n".join(section.body)
        for piece in split_text_into_pieces(
            body, max_chars=max_chunk_chars, overlap_chars=overlap_chars
        ):
            _append_chunk(chunks, f"{prefix}\n{piece}", heading=" > ".join(heading_path))
    elif not section.children:
        _append_chunk(chunks, prefix, heading=" > ".join(heading_path))
    for child in section.children:
        _emit_section_chunks(
            child,
            heading_path,
            chunks,
            max_chunk_chars=max_chunk_chars,
            overlap_chars=overlap_chars,
        )


def _append_chunk(chunks: list[DocumentChunk], content: str, *, heading: str) -> None:
    content = content.strip()
    if content:
        chunks.append(DocumentChunk(id=str(uuid4()), content=content, heading=heading))


def _joined_len(lines: list[str]) -> int:
    return sum(len(line) for line in lines) + len(lines) - 1


def _overlap_tail(lines: list[str], overlap_chars: int) -> list[str]:
    kept: list[str] = []
    kept_len = 0
    for line in reversed(lines):
        add = len(line) + (1 if kept else 0)
        if kept and kept_len + add > overlap_chars:
            break
        kept.insert(0, line)
        kept_len += add
    return kept
