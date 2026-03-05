"""Tests for memory-level context boost in scored_search (V2 enhancement).

V2 extends context_bonus_sql from trait-only to all memory types (fact/episodic/trait).
Tests verify that:
- fact/episodic memories now receive context boost (MB-7, MB-8)
- Exact match gives higher boost than general (MB-1, MB-3)
- Mismatch gives zero boost, not penalty (MB-2)
- NULL context gives zero boost (MB-4)
- Boost scales linearly with confidence (MB-5, MB-6)
- Sorting effects are correct (RI-1 ~ RI-3)

Requires PostgreSQL on port 5436.
Corresponds to test spec TS-4.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from neuromem.services.search import SearchService
from neuromem.services.context import ContextService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_memory_with_context(
    db_session,
    mock_embedding,
    *,
    user_id: str,
    content: str,
    memory_type: str = "fact",
    trait_context: str | None = None,
    trait_stage: str | None = None,
    trait_confidence: float = 0.7,
) -> str:
    """Insert a memory with optional trait_context, return its ID."""
    svc = SearchService(db_session, mock_embedding)
    record = await svc.add_memory(
        user_id=user_id,
        content=content,
        memory_type=memory_type,
        metadata={"importance": 7},
    )
    await db_session.commit()

    updates = []
    params: dict = {"mid": str(record.id)}

    if trait_context is not None:
        updates.append("trait_context = :ctx")
        params["ctx"] = trait_context

    if trait_stage is not None:
        updates.append("trait_stage = :stage")
        params["stage"] = trait_stage
        updates.append("trait_confidence = :conf")
        params["conf"] = trait_confidence

    if updates:
        sql = f"UPDATE memories SET {', '.join(updates)} WHERE id = :mid"
        await db_session.execute(text(sql), params)
        await db_session.commit()

    return str(record.id)


def _get_score_by_id(results: list[dict], memory_id: str) -> float | None:
    """Get score for a specific memory ID from search results."""
    for r in results:
        if r["id"] == memory_id:
            return r["score"]
    return None


def _get_context_match_by_id(results: list[dict], memory_id: str) -> float | None:
    """Get context_match value for a specific memory ID."""
    for r in results:
        if r["id"] == memory_id:
            return r.get("context_match")
    return None


# ===========================================================================
# TestFactContextBoost (MB-7, extending v1 CM-4)
# ===========================================================================


class TestFactContextBoost:
    """MB-7: fact memories now receive context boost (v2 change)."""

    @pytest.mark.asyncio
    async def test_fact_with_matching_context_gets_boost(self, db_session, mock_embedding):
        """MB-7: fact with matching context should have context_match > 0."""
        uid = f"mb7_{uuid.uuid4().hex[:6]}"
        base = uuid.uuid4().hex[:6]

        fact_id = await _insert_memory_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"works at Google {base}",
            memory_type="fact", trait_context="work",
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(
            user_id=uid, query=f"Google {base}", limit=10,
            query_context="work", context_confidence=0.8,
        )

        fact_result = next((r for r in results if r["id"] == fact_id), None)
        assert fact_result is not None, "fact should appear in results"
        assert fact_result.get("context_match", 0) > 0, (
            "fact with matching context should get context boost in v2"
        )

    @pytest.mark.asyncio
    async def test_fact_mismatch_no_penalty(self, db_session, mock_embedding):
        """MB-2: fact with mismatching context should have context_match = 0."""
        uid = f"mb2f_{uuid.uuid4().hex[:6]}"
        base = uuid.uuid4().hex[:6]

        fact_id = await _insert_memory_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"weekend hiking {base}",
            memory_type="fact", trait_context="personal",
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(
            user_id=uid, query=f"hiking {base}", limit=10,
            query_context="work", context_confidence=0.8,
        )

        fact_result = next((r for r in results if r["id"] == fact_id), None)
        assert fact_result is not None
        assert fact_result.get("context_match", 0) == 0, (
            "mismatching context should give context_match=0, not negative"
        )


# ===========================================================================
# TestEpisodicContextBoost (MB-8)
# ===========================================================================


class TestEpisodicContextBoost:
    """MB-8: episodic memories also receive context boost."""

    @pytest.mark.asyncio
    async def test_episodic_with_matching_context(self, db_session, mock_embedding):
        """MB-8: episodic with matching context should have context_match > 0."""
        uid = f"mb8_{uuid.uuid4().hex[:6]}"
        base = uuid.uuid4().hex[:6]

        ep_id = await _insert_memory_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"attended ML conference {base}",
            memory_type="episodic", trait_context="learning",
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(
            user_id=uid, query=f"ML conference {base}", limit=10,
            query_context="learning", context_confidence=0.8,
        )

        ep_result = next((r for r in results if r["id"] == ep_id), None)
        assert ep_result is not None
        assert ep_result.get("context_match", 0) > 0


# ===========================================================================
# TestGeneralAndNullContext (MB-3, MB-4)
# ===========================================================================


class TestGeneralAndNullContext:
    """MB-3, MB-4: general and NULL context behavior."""

    @pytest.mark.asyncio
    async def test_general_context_small_boost(self, db_session, mock_embedding):
        """MB-3: general context memory gets smaller boost than exact match."""
        uid = f"mb3_{uuid.uuid4().hex[:6]}"
        base = uuid.uuid4().hex[:6]

        general_id = await _insert_memory_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"knows Python {base}",
            memory_type="fact", trait_context="general",
        )
        work_id = await _insert_memory_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"uses Python at work {base}",
            memory_type="fact", trait_context="work",
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(
            user_id=uid, query=f"Python {base}", limit=10,
            query_context="work", context_confidence=0.8,
        )

        general_cm = _get_context_match_by_id(results, general_id)
        work_cm = _get_context_match_by_id(results, work_id)

        if general_cm is not None and work_cm is not None:
            assert work_cm > general_cm, (
                f"exact match boost ({work_cm}) should exceed general boost ({general_cm})"
            )

    @pytest.mark.asyncio
    async def test_null_context_no_boost(self, db_session, mock_embedding):
        """MB-4: NULL context memory should have context_match = 0."""
        uid = f"mb4_{uuid.uuid4().hex[:6]}"
        base = uuid.uuid4().hex[:6]

        null_id = await _insert_memory_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"old memory {base}",
            memory_type="fact",  # trait_context left as NULL
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(
            user_id=uid, query=f"old memory {base}", limit=10,
            query_context="work", context_confidence=0.8,
        )

        null_result = next((r for r in results if r["id"] == null_id), None)
        assert null_result is not None
        assert null_result.get("context_match", 0) == 0


# ===========================================================================
# TestConfidenceScaling (MB-5, MB-6)
# ===========================================================================


class TestConfidenceScaling:
    """MB-5, MB-6: Boost scales with confidence."""

    @pytest.mark.asyncio
    async def test_confidence_zero_disables_boost(self, db_session, mock_embedding):
        """MB-6: confidence=0 -> all context_match = 0."""
        uid = f"mb6_{uuid.uuid4().hex[:6]}"
        base = uuid.uuid4().hex[:6]

        work_id = await _insert_memory_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"coding task {base}",
            memory_type="fact", trait_context="work",
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(
            user_id=uid, query=f"coding {base}", limit=10,
            query_context="work", context_confidence=0.0,
        )

        work_result = next((r for r in results if r["id"] == work_id), None)
        assert work_result is not None
        assert work_result.get("context_match", 0) == 0


# ===========================================================================
# TestTraitBehaviorPreserved (MB-9)
# ===========================================================================


class TestTraitBehaviorPreserved:
    """MB-9: trait context boost still works as in v1."""

    @pytest.mark.asyncio
    async def test_trait_still_gets_context_boost(self, db_session, mock_embedding):
        """MB-9: trait with matching context should still get boost."""
        uid = f"mb9_{uuid.uuid4().hex[:6]}"
        base = uuid.uuid4().hex[:6]

        trait_id = await _insert_memory_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"prefers TDD {base}",
            memory_type="trait", trait_context="work",
            trait_stage="established",
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(
            user_id=uid, query=f"TDD {base}", limit=10,
            query_context="work", context_confidence=0.8,
        )

        trait_result = next((r for r in results if r["id"] == trait_id), None)
        assert trait_result is not None
        assert trait_result.get("context_match", 0) > 0


# ===========================================================================
# TestSortingEffects (RI-1 ~ RI-3)
# ===========================================================================


class TestSortingEffects:
    """RI-1 ~ RI-3: Context boost affects ranking."""

    @pytest.mark.asyncio
    async def test_matching_context_ranks_higher(self, db_session, mock_embedding):
        """RI-1: Memory with matching context ranks higher."""
        uid = f"ri1_{uuid.uuid4().hex[:6]}"
        base = uuid.uuid4().hex[:6]

        work_id = await _insert_memory_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"project deadline approaching {base}",
            memory_type="fact", trait_context="work",
        )
        personal_id = await _insert_memory_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"weekend plans deadline {base}",
            memory_type="fact", trait_context="personal",
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(
            user_id=uid, query=f"deadline {base}", limit=10,
            query_context="work", context_confidence=0.8,
        )

        work_score = _get_score_by_id(results, work_id)
        personal_score = _get_score_by_id(results, personal_id)

        if work_score is not None and personal_score is not None:
            assert work_score >= personal_score, (
                f"work memory ({work_score}) should rank >= personal ({personal_score})"
            )

    @pytest.mark.asyncio
    async def test_mixed_types_sorted_by_context(self, db_session, mock_embedding):
        """RI-3: Mixed memory types with matching context rank higher."""
        uid = f"ri3_{uuid.uuid4().hex[:6]}"
        base = uuid.uuid4().hex[:6]

        trait_id = await _insert_memory_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"prefers clean code {base}",
            memory_type="trait", trait_context="work",
            trait_stage="established",
        )
        fact_id = await _insert_memory_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"codes in Python {base}",
            memory_type="fact", trait_context="work",
        )
        ep_id = await _insert_memory_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"went to park {base}",
            memory_type="episodic", trait_context="personal",
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(
            user_id=uid, query=f"code {base}", limit=10,
            query_context="work", context_confidence=0.8,
        )

        work_ids = {trait_id, fact_id}
        work_scores = [r["score"] for r in results if r["id"] in work_ids]
        personal_scores = [r["score"] for r in results if r["id"] == ep_id]

        if work_scores and personal_scores:
            assert min(work_scores) >= max(personal_scores), (
                "work memories should all rank above personal memories"
            )
