from __future__ import annotations

import asyncpg

_MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     INTEGER PRIMARY KEY,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id  TEXT PRIMARY KEY,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id          BIGSERIAL PRIMARY KEY,
            session_id  TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
            seq         INTEGER NOT NULL,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (session_id, seq)
        );
        CREATE INDEX IF NOT EXISTS idx_chat_messages_session_seq
            ON chat_messages (session_id, seq DESC);

        CREATE TABLE IF NOT EXISTS tool_call_records (
            id            BIGSERIAL PRIMARY KEY,
            session_id    TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
            name          TEXT NOT NULL,
            input         TEXT NOT NULL,
            output        TEXT NOT NULL,
            status        TEXT NOT NULL,
            error         TEXT NOT NULL DEFAULT '',
            error_type    TEXT NOT NULL DEFAULT '',
            started_at    TIMESTAMPTZ,
            ended_at      TIMESTAMPTZ,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_tool_records_session
            ON tool_call_records (session_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS agent_runs (
            run_id            TEXT PRIMARY KEY,
            incident_id       TEXT NOT NULL,
            goal              TEXT NOT NULL,
            status            TEXT NOT NULL,
            stop_reason       TEXT NOT NULL DEFAULT '',
            iterations        INTEGER NOT NULL DEFAULT 0,
            tool_calls_count  INTEGER NOT NULL DEFAULT 0,
            started_at        TIMESTAMPTZ,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_agent_runs_incident
            ON agent_runs (incident_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS evidence (
            id          TEXT PRIMARY KEY,
            run_id      TEXT NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE,
            type        TEXT NOT NULL,
            source      TEXT NOT NULL DEFAULT '',
            summary     TEXT NOT NULL DEFAULT '',
            score       REAL NOT NULL DEFAULT 0.0,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_evidence_run ON evidence (run_id);

        CREATE TABLE IF NOT EXISTS chat_history (
            id          BIGSERIAL PRIMARY KEY,
            session_id  TEXT NOT NULL,
            question    TEXT NOT NULL,
            answer      TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_chat_history_session
            ON chat_history (session_id, created_at DESC);
        """,
    ),
]


async def run_migrations(pool: asyncpg.Pool) -> None:
    """Apply any pending migrations in version order within a single transaction."""
    async with pool.acquire() as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "  version INTEGER PRIMARY KEY,"
            "  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
            ")"
        )
        row = await conn.fetchrow(
            "SELECT COALESCE(MAX(version), 0) AS current FROM schema_migrations"
        )
        current = int(row["current"]) if row else 0

    for version, sql in _MIGRATIONS:
        if version <= current:
            continue
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)",
                    version,
                )
