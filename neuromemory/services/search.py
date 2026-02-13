"""Semantic search service - vector similarity search via pgvector."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from neuromemory.models.memory import Embedding
from neuromemory.providers.embedding import EmbeddingProvider

logger = logging.getLogger(__name__)

# Default decay rate: 30 days in seconds
DEFAULT_DECAY_RATE = 86400 * 30


class SearchService:
    def __init__(self, db: AsyncSession, embedding: EmbeddingProvider):
        self.db = db
        self._embedding = embedding

    async def add_memory(
        self,
        user_id: str,
        content: str,
        memory_type: str = "general",
        metadata: dict | None = None,
    ) -> Embedding:
        """Add a memory with its embedding vector."""
        vector = await self._embedding.embed(content)

        record = Embedding(
            user_id=user_id,
            content=content,
            embedding=vector,
            memory_type=memory_type,
            metadata_=metadata,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        memory_type: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
    ) -> list[dict]:
        """Semantic search for memories using cosine similarity."""
        query_vector = await self._embedding.embed(query)

        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in query_vector):
            raise ValueError("Invalid vector data: must contain only numeric values")

        vector_str = f"[{','.join(str(float(v)) for v in query_vector)}]"

        filters = "user_id = :user_id"
        params: dict = {"user_id": user_id, "limit": limit}

        if memory_type:
            filters += " AND memory_type = :memory_type"
            params["memory_type"] = memory_type

        if created_after:
            filters += " AND created_at >= :created_after"
            params["created_after"] = created_after

        if created_before:
            filters += " AND created_at < :created_before"
            params["created_before"] = created_before

        sql = text(
            f"""
            SELECT id, content, memory_type, metadata, created_at,
                   1 - (embedding <=> '{vector_str}'::vector) AS score
            FROM embeddings
            WHERE {filters}
            ORDER BY embedding <=> '{vector_str}'::vector
            LIMIT :limit
        """
        )

        result = await self.db.execute(sql, params)
        rows = result.fetchall()

        results = [
            {
                "id": str(row.id),
                "content": row.content,
                "memory_type": row.memory_type,
                "metadata": row.metadata,
                "created_at": row.created_at,
                "score": round(float(row.score), 4),
            }
            for row in rows
        ]

        # Update access tracking asynchronously
        if results:
            await self._update_access_tracking([r["id"] for r in results])

        return results

    async def scored_search(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        memory_type: str | None = None,
        decay_rate: float = DEFAULT_DECAY_RATE,
    ) -> list[dict]:
        """Three-factor scored search: relevance x recency x importance.

        Score = relevance * recency * importance
        - relevance: cosine similarity (0-1)
        - recency: exponential decay e^(-t/decay_rate), emotional arousal slows decay
        - importance: from metadata (1-10 scaled to 0.1-1.0), default 0.5
        """
        query_vector = await self._embedding.embed(query)

        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in query_vector):
            raise ValueError("Invalid vector data: must contain only numeric values")

        vector_str = f"[{','.join(str(float(v)) for v in query_vector)}]"

        filters = "user_id = :user_id"
        params: dict = {"user_id": user_id, "limit": limit, "decay_rate": decay_rate}

        if memory_type:
            filters += " AND memory_type = :memory_type"
            params["memory_type"] = memory_type

        # Emotional arousal slows decay: effective_decay = decay_rate * (1 + arousal * 0.5)
        sql = text(
            f"""
            SELECT id, content, memory_type, metadata, created_at,
                   access_count, last_accessed_at,
                   (1 - (embedding <=> '{vector_str}'::vector)) AS relevance,
                   EXP(
                       -EXTRACT(EPOCH FROM (NOW() - created_at))
                       / (:decay_rate * (1 + COALESCE((metadata->'emotion'->>'arousal')::float, 0) * 0.5))
                   ) AS recency,
                   COALESCE((metadata->>'importance')::float / 10.0, 0.5) AS importance,
                   (1 - (embedding <=> '{vector_str}'::vector))
                   * EXP(
                       -EXTRACT(EPOCH FROM (NOW() - created_at))
                       / (:decay_rate * (1 + COALESCE((metadata->'emotion'->>'arousal')::float, 0) * 0.5))
                   )
                   * COALESCE((metadata->>'importance')::float / 10.0, 0.5) AS score
            FROM embeddings
            WHERE {filters}
            ORDER BY score DESC
            LIMIT :limit
        """
        )

        result = await self.db.execute(sql, params)
        rows = result.fetchall()

        results = [
            {
                "id": str(row.id),
                "content": row.content,
                "memory_type": row.memory_type,
                "metadata": row.metadata,
                "created_at": row.created_at,
                "relevance": round(float(row.relevance), 4),
                "recency": round(float(row.recency), 4),
                "importance": round(float(row.importance), 4),
                "score": round(float(row.score), 4),
            }
            for row in rows
        ]

        # Update access tracking
        if results:
            await self._update_access_tracking([r["id"] for r in results])

        return results

    async def _update_access_tracking(self, ids: list[str]) -> None:
        """Update access_count and last_accessed_at for retrieved memories."""
        if not ids:
            return
        try:
            # Use individual parameterized placeholders for safety
            placeholders = ", ".join(f":id_{i}" for i in range(len(ids)))
            params = {f"id_{i}": id_ for i, id_ in enumerate(ids)}
            sql = text(f"""
                UPDATE embeddings
                SET access_count = access_count + 1,
                    last_accessed_at = NOW()
                WHERE id IN ({placeholders})
            """)
            await self.db.execute(sql, params)
            await self.db.commit()
        except Exception as e:
            logger.warning("Failed to update access tracking: %s", e)
