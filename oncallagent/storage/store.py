from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

import asyncpg

from oncallagent.agent.harness import AgentState, Evidence, ToolCallRecord, ToolCallStatus
from oncallagent.storage.migrations import run_migrations


class ConversationStore(Protocol):
    """Structural interface for session persistence backends."""

    async def ensure_session(self, session_id: str) -> None:
        """Create session row if it does not exist."""
        ...

    async def save_message(
        self, session_id: str, seq: int, role: str, content: str
    ) -> None:
        """Persist a single chat message."""
        ...

    async def load_recent_messages(
        self, session_id: str, limit: int = 6
    ) -> list[dict]:
        """Load the most recent N messages for a session (oldest-first, with seq)."""
        ...

    async def save_tool_record(
        self, session_id: str, record: ToolCallRecord
    ) -> None:
        """Persist a tool call audit record."""
        ...

    async def load_tool_records(
        self, session_id: str
    ) -> list[ToolCallRecord]:
        """Load all tool call records for a session."""
        ...

    async def save_agent_run(self, state: AgentState, *, started_at: datetime | None = None) -> None:
        """Persist or update an agent run record from AgentState."""
        ...

    async def save_evidence(self, evidence: Evidence) -> None:
        """Persist an evidence record."""
        ...

    async def save_chat_history(
        self, session_id: str, question: str, answer: str
    ) -> None:
        """Persist a fallback Q&A pair."""
        ...

    async def close(self) -> None:
        """Release resources (e.g. connection pool)."""
        ...


class PostgresStore:
    """Concrete PostgreSQL-backed implementation of ConversationStore.

    Operates on an already-created asyncpg Pool."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def close(self) -> None:
        await self._pool.close()

    # ------------------------------------------------------------------ session

    async def ensure_session(self, session_id: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO sessions (session_id) VALUES ($1) "
                "ON CONFLICT DO NOTHING",
                session_id,
            )

    # ----------------------------------------------------------------- messages

    async def save_message(
        self, session_id: str, seq: int, role: str, content: str
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chat_messages (session_id, seq, role, content) "
                "VALUES ($1, $2, $3, $4) "
                "ON CONFLICT (session_id, seq) DO NOTHING",
                session_id, seq, role, content,
            )

    async def load_recent_messages(
        self, session_id: str, limit: int = 6
    ) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT seq, role, content FROM chat_messages "
                "WHERE session_id = $1 "
                "ORDER BY seq DESC LIMIT $2",
                session_id, limit,
            )
        return [
            {"seq": row["seq"], "role": row["role"], "content": row["content"]}
            for row in reversed(list(rows))
        ]

    # --------------------------------------------------------------- tool calls

    async def save_tool_record(
        self, session_id: str, record: ToolCallRecord
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO tool_call_records "
                "(session_id, name, input, output, status, error, error_type, "
                " started_at, ended_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                session_id,
                record.name,
                record.input,
                record.output,
                record.status.value,
                record.error,
                record.error_type,
                record.started_at,
                record.ended_at,
            )

    async def load_tool_records(
        self, session_id: str
    ) -> list[ToolCallRecord]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT name, input, output, status, error, error_type, "
                "started_at, ended_at "
                "FROM tool_call_records "
                "WHERE session_id = $1 ORDER BY created_at ASC",
                session_id,
            )
        return [
            ToolCallRecord(
                name=row["name"],
                input=row["input"],
                output=row["output"],
                status=ToolCallStatus(row["status"]),
                error=row["error"],
                error_type=row["error_type"],
                started_at=row["started_at"],
                ended_at=row["ended_at"],
            )
            for row in rows
        ]

    # -------------------------------------------------------------- agent runs

    async def save_agent_run(
        self, state: AgentState, *, started_at: datetime | None = None
    ) -> None:
        run_id = state.incident_id
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO agent_runs "
                "(run_id, incident_id, goal, status, stop_reason, "
                " iterations, tool_calls_count, started_at, created_at, updated_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) "
                "ON CONFLICT (run_id) DO UPDATE SET "
                "  status = EXCLUDED.status, "
                "  stop_reason = EXCLUDED.stop_reason, "
                "  iterations = EXCLUDED.iterations, "
                "  tool_calls_count = EXCLUDED.tool_calls_count, "
                "  updated_at = EXCLUDED.updated_at",
                run_id,
                state.incident_id,
                state.goal,
                state.status.value,
                state.stop_reason.value,
                state.usage.iterations,
                state.usage.tool_calls,
                started_at or state.created_at,
                state.created_at,
                now,
            )

    # ---------------------------------------------------------------- evidence

    async def save_evidence(self, evidence: Evidence) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO evidence (id, run_id, type, source, summary, score) "
                "VALUES ($1, $2, $3, $4, $5, $6) "
                "ON CONFLICT (id) DO NOTHING",
                evidence.id,
                evidence.run_id,
                evidence.type.value,
                evidence.source,
                evidence.summary,
                evidence.score,
            )

    # ------------------------------------------------------------ chat history

    async def save_chat_history(
        self, session_id: str, question: str, answer: str
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chat_history (session_id, question, answer) "
                "VALUES ($1, $2, $3)",
                session_id, question, answer,
            )


class LazyPostgresStore:
    """Wraps PostgresStore with lazy pool creation.

    The asyncpg pool must be created inside the same event loop that will use it
    (FastAPI's loop).  This wrapper defers pool creation until the first DB
    operation, which always happens inside a request handler on the correct loop.
    """

    def __init__(self, database_url: str, *, min_size: int = 2, max_size: int = 10) -> None:
        self._database_url = database_url
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None
        self._store: PostgresStore | None = None

    async def _ensure_pool(self) -> PostgresStore | None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=self._min_size,
                max_size=self._max_size,
            )
            await run_migrations(self._pool)
            self._store = PostgresStore(self._pool)
        return self._store

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._store = None

    # ------------------------------------------------------------------ session

    async def ensure_session(self, session_id: str) -> None:
        store = await self._ensure_pool()
        if store is not None:
            await store.ensure_session(session_id)

    # ----------------------------------------------------------------- messages

    async def save_message(
        self, session_id: str, seq: int, role: str, content: str
    ) -> None:
        store = await self._ensure_pool()
        if store is not None:
            await store.save_message(session_id, seq, role, content)

    async def load_recent_messages(
        self, session_id: str, limit: int = 6
    ) -> list[dict]:
        store = await self._ensure_pool()
        if store is not None:
            return await store.load_recent_messages(session_id, limit)
        return []

    # --------------------------------------------------------------- tool calls

    async def save_tool_record(
        self, session_id: str, record: ToolCallRecord
    ) -> None:
        store = await self._ensure_pool()
        if store is not None:
            await store.save_tool_record(session_id, record)

    async def load_tool_records(
        self, session_id: str
    ) -> list[ToolCallRecord]:
        store = await self._ensure_pool()
        if store is not None:
            return await store.load_tool_records(session_id)
        return []

    # -------------------------------------------------------------- agent runs

    async def save_agent_run(
        self, state: AgentState, *, started_at: datetime | None = None
    ) -> None:
        store = await self._ensure_pool()
        if store is not None:
            await store.save_agent_run(state, started_at=started_at)

    # ---------------------------------------------------------------- evidence

    async def save_evidence(self, evidence: Evidence) -> None:
        store = await self._ensure_pool()
        if store is not None:
            await store.save_evidence(evidence)

    # ------------------------------------------------------------ chat history

    async def save_chat_history(
        self, session_id: str, question: str, answer: str
    ) -> None:
        store = await self._ensure_pool()
        if store is not None:
            await store.save_chat_history(session_id, question, answer)
