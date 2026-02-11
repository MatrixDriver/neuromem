"""Semantic search service - vector similarity search via pgvector."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from neuromemory.models.memory import Embedding
from neuromemory.providers.embedding import EmbeddingProvider


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

        return [
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
