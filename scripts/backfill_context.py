"""Backfill trait_context for existing fact/episodic memories.

Usage:
    uv run python scripts/backfill_context.py --database-url DATABASE_URL --embedding-api-key API_KEY [--force]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from neuromem.providers.siliconflow import SiliconFlowEmbedding
from neuromem.services.context import ContextService, cosine_similarity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 100


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill trait_context for fact/episodic memories")
    parser.add_argument("--database-url", required=True, help="PostgreSQL async connection URL")
    parser.add_argument("--embedding-api-key", required=True, help="SiliconFlow API key for prototype initialization")
    parser.add_argument("--force", action="store_true", help="Overwrite existing trait_context values")
    args = parser.parse_args()

    engine = create_async_engine(args.database_url)
    embedding = SiliconFlowEmbedding(api_key=args.embedding_api_key)
    ctx_service = ContextService(embedding)
    await ctx_service.ensure_prototypes()

    if not ctx_service._prototypes:
        logger.error("Failed to initialize context prototypes, aborting")
        await engine.dispose()
        return

    filter_clause = "trait_context IS NULL" if not args.force else "TRUE"

    stats: dict[str, int] = {"total": 0, "updated": 0}
    context_counts: dict[str, int] = {}
    offset = 0

    async with engine.connect() as conn:
        while True:
            result = await conn.execute(
                text(
                    f"SELECT id, embedding FROM memories "
                    f"WHERE memory_type IN ('fact', 'episodic') AND ({filter_clause}) "
                    f"ORDER BY id LIMIT :batch OFFSET :offset"
                ),
                {"batch": BATCH_SIZE, "offset": offset},
            )
            rows = result.fetchall()
            if not rows:
                break

            updates: list[dict] = []
            for row in rows:
                stats["total"] += 1
                raw_embedding = row.embedding
                if isinstance(raw_embedding, str):
                    embedding_vector = [float(x) for x in json.loads(raw_embedding)]
                else:
                    embedding_vector = [float(x) for x in raw_embedding]

                best_ctx = "general"
                best_score = -1.0
                second_score = -1.0
                for ctx, proto in ctx_service._prototypes.items():
                    sim = cosine_similarity(embedding_vector, proto)
                    if sim > best_score:
                        second_score = best_score
                        best_score = sim
                        best_ctx = ctx
                    elif sim > second_score:
                        second_score = sim

                margin = best_score - second_score
                if margin < ContextService.MARGIN_THRESHOLD:
                    best_ctx = "general"

                updates.append({"mid": str(row.id), "ctx": best_ctx})
                context_counts[best_ctx] = context_counts.get(best_ctx, 0) + 1

            for upd in updates:
                await conn.execute(
                    text("UPDATE memories SET trait_context = :ctx WHERE id = :mid::uuid"),
                    upd,
                )
            await conn.commit()
            stats["updated"] += len(updates)

            logger.info("Processed %d memories (batch offset=%d)", stats["total"], offset)
            offset += BATCH_SIZE

    await engine.dispose()

    logger.info("Backfill complete: %d total, %d updated", stats["total"], stats["updated"])
    logger.info("Context distribution: %s", context_counts)


if __name__ == "__main__":
    asyncio.run(main())
