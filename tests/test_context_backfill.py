"""Tests for context backfill logic.

Covers:
- TS-3.1: Backfill algorithm (BF-1 ~ BF-4)
- TS-3.2: Database integration (BI-1 ~ BI-6)

Unit tests use inline backfill logic. Integration tests require PostgreSQL on port 5436.
"""

from __future__ import annotations

import math
import uuid

import pytest
from sqlalchemy import text

from neuromem.services.context import ContextService, cosine_similarity
from neuromem.services.search import SearchService


# ---------------------------------------------------------------------------
# Inline backfill logic (mirrors expected implementation in scripts/backfill_context.py)
# ---------------------------------------------------------------------------

MARGIN_THRESHOLD = ContextService.MARGIN_THRESHOLD


def backfill_classify(
    embedding: list[float],
    prototypes: dict[str, list[float]],
    margin_threshold: float = MARGIN_THRESHOLD,
) -> str:
    """Classify a memory's context based on embedding similarity to prototypes.

    Returns the best matching context label, or 'general' if margin is insufficient.
    """
    if not embedding or not prototypes:
        return "general"

    similarities = {
        ctx: cosine_similarity(embedding, proto)
        for ctx, proto in prototypes.items()
    }
    sorted_items = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
    best_ctx, best_score = sorted_items[0]
    second_score = sorted_items[1][1] if len(sorted_items) > 1 else 0.0
    margin = best_score - second_score

    if margin < margin_threshold:
        return "general"
    return best_ctx


# ---------------------------------------------------------------------------
# Mock prototypes (orthogonal 4D vectors for precise control)
# ---------------------------------------------------------------------------

MOCK_PROTOTYPES = {
    "work":     [1.0, 0.0, 0.0, 0.0],
    "personal": [0.0, 1.0, 0.0, 0.0],
    "social":   [0.0, 0.0, 1.0, 0.0],
    "learning": [0.0, 0.0, 0.0, 1.0],
}


# ===========================================================================
# TestBackfillClassify (BF-1 ~ BF-4)
# ===========================================================================


class TestBackfillClassify:
    """BF-1 ~ BF-4: Backfill classification logic."""

    def test_highest_similarity_wins(self):
        """BF-1: Embedding closest to 'work' prototype -> 'work'."""
        embedding = [0.9, 0.1, 0.0, 0.0]
        result = backfill_classify(embedding, MOCK_PROTOTYPES)
        assert result == "work"

    def test_personal_classification(self):
        """BF-1 variant: Personal classification."""
        embedding = [0.0, 0.9, 0.1, 0.0]
        result = backfill_classify(embedding, MOCK_PROTOTYPES)
        assert result == "personal"

    def test_learning_classification(self):
        """BF-1 variant: Learning classification."""
        embedding = [0.1, 0.0, 0.0, 0.9]
        result = backfill_classify(embedding, MOCK_PROTOTYPES)
        assert result == "learning"

    def test_below_threshold_general(self):
        """BF-2: All similarities roughly equal -> margin too low -> 'general'."""
        embedding = [0.5, 0.5, 0.5, 0.5]
        result = backfill_classify(embedding, MOCK_PROTOTYPES)
        assert result == "general"

    def test_margin_just_below_threshold(self):
        """BF-2 variant: Margin just below threshold -> 'general'."""
        # Two similar dimensions, margin < threshold
        embedding = [0.51, 0.50, 0.0, 0.0]
        result = backfill_classify(embedding, MOCK_PROTOTYPES, margin_threshold=0.05)
        # With these values, margin is very small
        # cosine(work)~0.713, cosine(personal)~0.699, margin~0.014 < 0.05
        assert result == "general"

    def test_idempotent(self):
        """BF-3: Running classification twice gives the same result."""
        embedding = [0.9, 0.1, 0.0, 0.0]
        result1 = backfill_classify(embedding, MOCK_PROTOTYPES)
        result2 = backfill_classify(embedding, MOCK_PROTOTYPES)
        assert result1 == result2

    def test_empty_embedding(self):
        """Edge: Empty embedding -> 'general'."""
        assert backfill_classify([], MOCK_PROTOTYPES) == "general"

    def test_zero_embedding(self):
        """Edge: Zero vector -> 'general' (cosine_similarity returns 0)."""
        embedding = [0.0, 0.0, 0.0, 0.0]
        result = backfill_classify(embedding, MOCK_PROTOTYPES)
        assert result == "general"

    def test_no_prototypes(self):
        """Edge: No prototypes -> 'general'."""
        assert backfill_classify([1.0, 0.0], {}) == "general"


# ===========================================================================
# Integration tests: backfill updates database (requires DB)
# ===========================================================================


async def _insert_fact_with_embedding(
    db_session,
    mock_embedding,
    *,
    user_id: str,
    content: str,
    trait_context: str | None = None,
) -> str:
    """Insert a fact memory and return its ID."""
    svc = SearchService(db_session, mock_embedding)
    record = await svc.add_memory(
        user_id=user_id,
        content=content,
        memory_type="fact",
        metadata={"importance": 5},
    )
    await db_session.commit()

    if trait_context is not None:
        await db_session.execute(
            text("UPDATE memories SET trait_context = :ctx WHERE id = :mid"),
            {"ctx": trait_context, "mid": str(record.id)},
        )
        await db_session.commit()

    return str(record.id)


@pytest.mark.asyncio
async def test_backfill_updates_null_records(db_session, mock_embedding):
    """BI-1: Backfill updates trait_context for NULL records."""
    uid = f"bf_null_{uuid.uuid4().hex[:6]}"

    # Insert facts without trait_context (NULL)
    id1 = await _insert_fact_with_embedding(
        db_session, mock_embedding, user_id=uid, content=f"fact one {uid}",
    )
    id2 = await _insert_fact_with_embedding(
        db_session, mock_embedding, user_id=uid, content=f"fact two {uid}",
    )

    # Verify initially NULL
    rows = (await db_session.execute(
        text("SELECT id, trait_context FROM memories WHERE user_id = :uid AND memory_type = 'fact'"),
        {"uid": uid},
    )).fetchall()
    assert all(r.trait_context is None for r in rows)

    # Simulate backfill: update all NULL trait_context to 'general'
    # (In real backfill, would compute from prototype similarity)
    await db_session.execute(
        text(
            "UPDATE memories SET trait_context = 'general' "
            "WHERE user_id = :uid AND memory_type = 'fact' AND trait_context IS NULL"
        ),
        {"uid": uid},
    )
    await db_session.commit()

    # Verify updated
    rows = (await db_session.execute(
        text("SELECT trait_context FROM memories WHERE user_id = :uid AND memory_type = 'fact'"),
        {"uid": uid},
    )).fetchall()
    assert all(r.trait_context is not None for r in rows)


@pytest.mark.asyncio
async def test_backfill_skips_already_labeled(db_session, mock_embedding):
    """BI-2: Backfill should not overwrite already-labeled records (default mode)."""
    uid = f"bf_skip_{uuid.uuid4().hex[:6]}"

    # Insert one labeled fact + one unlabeled fact
    id_labeled = await _insert_fact_with_embedding(
        db_session, mock_embedding, user_id=uid,
        content=f"labeled fact {uid}", trait_context="work",
    )
    id_unlabeled = await _insert_fact_with_embedding(
        db_session, mock_embedding, user_id=uid,
        content=f"unlabeled fact {uid}",
    )

    # Simulate default backfill (only NULL records)
    await db_session.execute(
        text(
            "UPDATE memories SET trait_context = 'general' "
            "WHERE user_id = :uid AND memory_type = 'fact' AND trait_context IS NULL"
        ),
        {"uid": uid},
    )
    await db_session.commit()

    # Labeled fact should still be 'work'
    row = (await db_session.execute(
        text("SELECT trait_context FROM memories WHERE id = :mid"),
        {"mid": id_labeled},
    )).fetchone()
    assert row.trait_context == "work"

    # Unlabeled fact should now have 'general'
    row = (await db_session.execute(
        text("SELECT trait_context FROM memories WHERE id = :mid"),
        {"mid": id_unlabeled},
    )).fetchone()
    assert row.trait_context == "general"


@pytest.mark.asyncio
async def test_backfill_trait_not_affected(db_session, mock_embedding):
    """BI-3: Trait memories should not be processed by fact/episodic backfill."""
    uid = f"bf_trait_{uuid.uuid4().hex[:6]}"

    # Insert a trait with existing context
    svc = SearchService(db_session, mock_embedding)
    record = await svc.add_memory(
        user_id=uid, content=f"trait {uid}",
        memory_type="trait", metadata={"importance": 7},
    )
    await db_session.commit()
    await db_session.execute(
        text("UPDATE memories SET trait_context = 'personal', trait_stage = 'established' WHERE id = :mid"),
        {"mid": str(record.id)},
    )
    await db_session.commit()

    # Backfill targeting fact/episodic only
    await db_session.execute(
        text(
            "UPDATE memories SET trait_context = 'general' "
            "WHERE user_id = :uid AND memory_type IN ('fact', 'episodic') AND trait_context IS NULL"
        ),
        {"uid": uid},
    )
    await db_session.commit()

    # Trait should be untouched
    row = (await db_session.execute(
        text("SELECT trait_context FROM memories WHERE id = :mid"),
        {"mid": str(record.id)},
    )).fetchone()
    assert row.trait_context == "personal"
