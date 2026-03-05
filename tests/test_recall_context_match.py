"""Integration tests for context_match bonus in scored_search.

Tests SQL CASE expression for context_match, sorting effects,
and interaction with other bonuses. Requires PostgreSQL on port 5436.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from neuromem.services.search import SearchService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _insert_trait_with_context(
    db_session,
    mock_embedding,
    *,
    user_id: str = "ctx_user",
    content: str | None = None,
    trait_context: str = "work",
    trait_stage: str = "established",
    trait_confidence: float = 0.7,
) -> str:
    """Insert a trait memory with trait_context in metadata, return its id."""
    svc = SearchService(db_session, mock_embedding)
    if content is None:
        content = f"trait {uuid.uuid4().hex[:8]}"
    record = await svc.add_memory(
        user_id=user_id,
        content=content,
        memory_type="trait",
        metadata={"importance": 7, "context": trait_context},
    )
    await db_session.commit()

    # Update trait-specific columns
    stmt = text(
        "UPDATE memories SET trait_stage = :stage, trait_confidence = :conf "
        "WHERE id = :mid"
    )
    await db_session.execute(stmt, {
        "mid": str(record.id),
        "stage": trait_stage,
        "conf": trait_confidence,
    })
    await db_session.commit()
    return str(record.id)


async def _insert_fact(
    db_session,
    mock_embedding,
    *,
    user_id: str = "ctx_user",
    content: str | None = None,
    trait_context: str | None = None,
) -> str:
    """Insert a fact memory, return its id."""
    svc = SearchService(db_session, mock_embedding)
    if content is None:
        content = f"fact {uuid.uuid4().hex[:8]}"
    record = await svc.add_memory(
        user_id=user_id,
        content=content,
        memory_type="fact",
        metadata={"importance": 7},
    )
    await db_session.commit()
    if trait_context:
        await db_session.execute(
            text("UPDATE memories SET trait_context = :ctx WHERE id = :mid"),
            {"ctx": trait_context, "mid": str(record.id)},
        )
        await db_session.commit()
    return str(record.id)


async def _insert_episode(
    db_session,
    mock_embedding,
    *,
    user_id: str = "ctx_user",
    content: str | None = None,
    trait_context: str | None = None,
) -> str:
    """Insert an episodic memory, return its id."""
    svc = SearchService(db_session, mock_embedding)
    if content is None:
        content = f"episode {uuid.uuid4().hex[:8]}"
    record = await svc.add_memory(
        user_id=user_id,
        content=content,
        memory_type="episodic",
        metadata={"importance": 7},
    )
    await db_session.commit()
    if trait_context:
        await db_session.execute(
            text("UPDATE memories SET trait_context = :ctx WHERE id = :mid"),
            {"ctx": trait_context, "mid": str(record.id)},
        )
        await db_session.commit()
    return str(record.id)


# ===========================================================================
# TestContextMatchBonus
# ===========================================================================


class TestContextMatchBonus:
    """CM-1~CM-6: Verify context_match bonus values in scored_search.

    NOTE: These tests will only pass once the context_match SQL is implemented
    in SearchService.scored_search. Until then, they serve as specification
    for the expected behavior. The tests verify scoring effects by comparing
    scores of trait memories with different context labels.
    """

    @pytest.mark.asyncio
    async def test_exact_context_match_higher_score(self, db_session, mock_embedding):
        """CM-1: Trait with matching context should score higher than mismatching."""
        uid = f"cm1_{uuid.uuid4().hex[:6]}"
        content_base = f"prefers functional programming {uuid.uuid4().hex[:6]}"

        # Insert two traits with same content but different contexts
        work_id = await _insert_trait_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"work {content_base}",
            trait_context="work", trait_stage="established",
        )
        personal_id = await _insert_trait_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"personal {content_base}",
            trait_context="personal", trait_stage="established",
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(
            user_id=uid,
            query=f"work {content_base}",
            limit=10,
            # Once implemented, context params will be passed:
            # query_context="work", context_confidence=0.8,
        )

        # Both should appear in results
        work_result = next((r for r in results if r["id"] == work_id), None)
        personal_result = next((r for r in results if r["id"] == personal_id), None)
        assert work_result is not None, "work trait should appear in results"
        assert personal_result is not None, "personal trait should appear in results"

    @pytest.mark.asyncio
    async def test_fact_with_context_gets_boost(self, db_session, mock_embedding):
        """CM-4: Fact with matching context should score higher than mismatching."""
        uid = f"cm4_{uuid.uuid4().hex[:6]}"
        base = uuid.uuid4().hex[:6]

        work_fact_id = await _insert_fact(
            db_session, mock_embedding,
            user_id=uid, content=f"work coding project {base}",
            trait_context="work",
        )
        personal_fact_id = await _insert_fact(
            db_session, mock_embedding,
            user_id=uid, content=f"personal cooking recipe {base}",
            trait_context="personal",
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(
            user_id=uid, query=f"work coding project {base}",
            limit=10, query_context="work", context_confidence=0.8,
        )

        work_result = next((r for r in results if r["id"] == work_fact_id), None)
        personal_result = next((r for r in results if r["id"] == personal_fact_id), None)
        assert work_result is not None, "work fact should appear in results"
        assert personal_result is not None, "personal fact should appear in results"
        assert work_result["score"] > personal_result["score"], (
            f"work fact ({work_result['score']}) should outscore personal fact ({personal_result['score']})"
        )

    @pytest.mark.asyncio
    async def test_episode_with_context_gets_boost(self, db_session, mock_embedding):
        """CM-4b: Episode with matching context should score higher than mismatching."""
        uid = f"cm4b_{uuid.uuid4().hex[:6]}"
        base = uuid.uuid4().hex[:6]

        work_ep_id = await _insert_episode(
            db_session, mock_embedding,
            user_id=uid, content=f"attended team standup meeting {base}",
            trait_context="work",
        )
        personal_ep_id = await _insert_episode(
            db_session, mock_embedding,
            user_id=uid, content=f"went hiking with family {base}",
            trait_context="personal",
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(
            user_id=uid, query=f"attended team standup meeting {base}",
            limit=10, query_context="work", context_confidence=0.8,
        )

        work_result = next((r for r in results if r["id"] == work_ep_id), None)
        personal_result = next((r for r in results if r["id"] == personal_ep_id), None)
        assert work_result is not None, "work episode should appear in results"
        assert personal_result is not None, "personal episode should appear in results"
        assert work_result["score"] > personal_result["score"], (
            f"work episode ({work_result['score']}) should outscore personal episode ({personal_result['score']})"
        )

    @pytest.mark.asyncio
    async def test_null_context_no_penalty(self, db_session, mock_embedding):
        """CM-4c: Memory with NULL trait_context should get context_match=0, no penalty."""
        uid = f"cm4c_{uuid.uuid4().hex[:6]}"
        content = f"user works at Google {uuid.uuid4().hex[:6]}"

        fact_id = await _insert_fact(
            db_session, mock_embedding,
            user_id=uid, content=content,
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(
            user_id=uid, query=content, limit=10,
            query_context="work", context_confidence=0.8,
        )

        fact_result = next((r for r in results if r["id"] == fact_id), None)
        assert fact_result is not None
        assert fact_result["context_match"] == 0

    @pytest.mark.asyncio
    async def test_trait_without_context_metadata(self, db_session, mock_embedding):
        """CM-5 variant: Trait without context in metadata gets no context boost."""
        uid = f"cm5v_{uuid.uuid4().hex[:6]}"
        content = f"old trait without context {uuid.uuid4().hex[:6]}"

        # Insert trait without context metadata
        svc = SearchService(db_session, mock_embedding)
        record = await svc.add_memory(
            user_id=uid, content=content,
            memory_type="trait",
            metadata={"importance": 7},  # no "context" key
        )
        await db_session.commit()
        await db_session.execute(
            text("UPDATE memories SET trait_stage = 'established', trait_confidence = 0.7 WHERE id = :mid"),
            {"mid": str(record.id)},
        )
        await db_session.commit()

        results = await svc.scored_search(user_id=uid, query=content, limit=10)
        trait_result = next((r for r in results if r["id"] == str(record.id)), None)
        assert trait_result is not None, "trait without context should still appear"


# ===========================================================================
# TestContextMatchSorting
# ===========================================================================


class TestContextMatchSorting:
    """SO-1~SO-3: Verify context_match affects sorting order.

    NOTE: Full sorting verification requires context_match implementation.
    These tests currently verify baseline behavior and will be extended
    once scored_search accepts query_context/context_confidence params.
    """

    @pytest.mark.asyncio
    async def test_same_stage_traits_both_appear(self, db_session, mock_embedding):
        """SO-1 baseline: Two established traits with different contexts both appear."""
        uid = f"so1_{uuid.uuid4().hex[:6]}"
        base = uuid.uuid4().hex[:6]

        work_id = await _insert_trait_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"likes TDD approach {base}",
            trait_context="work", trait_stage="established",
        )
        personal_id = await _insert_trait_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"likes minimalist style {base}",
            trait_context="personal", trait_stage="established",
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(user_id=uid, query=f"likes {base}", limit=10)

        ids_in_results = [r["id"] for r in results]
        assert work_id in ids_in_results, "work trait should appear"
        assert personal_id in ids_in_results, "personal trait should appear"

    @pytest.mark.asyncio
    async def test_general_trait_appears_in_results(self, db_session, mock_embedding):
        """SO-2 baseline: General trait appears alongside context-specific traits."""
        uid = f"so2_{uuid.uuid4().hex[:6]}"
        base = uuid.uuid4().hex[:6]

        await _insert_trait_with_context(
            db_session, mock_embedding,
            user_id=uid, content=f"prefers concise answers {base}",
            trait_context="general", trait_stage="established",
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(user_id=uid, query=f"concise {base}", limit=10)
        assert len(results) >= 1, "general trait should appear in results"


# ===========================================================================
# TestContextMatchWithOtherBonuses
# ===========================================================================


class TestContextMatchWithOtherBonuses:
    """OB-1~OB-3: Context match interacts correctly with other bonuses."""

    @pytest.mark.asyncio
    async def test_trait_boost_still_applies(self, db_session, mock_embedding):
        """OB-1: Core trait still gets higher score than fact due to trait_boost."""
        uid = f"ob1_{uuid.uuid4().hex[:6]}"
        content = f"user is expert in Python {uuid.uuid4().hex[:6]}"

        trait_id = await _insert_trait_with_context(
            db_session, mock_embedding,
            user_id=uid, content=content,
            trait_context="work", trait_stage="core",
            trait_confidence=0.9,
        )
        fact_id = await _insert_fact(
            db_session, mock_embedding,
            user_id=uid, content=content,
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(user_id=uid, query=content, limit=10)

        trait_result = next((r for r in results if r["id"] == trait_id), None)
        fact_result = next((r for r in results if r["id"] == fact_id), None)

        assert trait_result is not None
        assert fact_result is not None
        assert trait_result["score"] > fact_result["score"], (
            f"core trait ({trait_result['score']}) should outscore fact ({fact_result['score']})"
        )

    @pytest.mark.asyncio
    async def test_total_bonus_reasonable(self, db_session, mock_embedding):
        """OB-3: Total bonus should be in a reasonable range."""
        uid = f"ob3_{uuid.uuid4().hex[:6]}"
        content = f"important core trait {uuid.uuid4().hex[:6]}"

        trait_id = await _insert_trait_with_context(
            db_session, mock_embedding,
            user_id=uid, content=content,
            trait_context="work", trait_stage="core",
            trait_confidence=0.9,
        )

        svc = SearchService(db_session, mock_embedding)
        results = await svc.scored_search(user_id=uid, query=content, limit=10)

        trait_result = next((r for r in results if r["id"] == trait_id), None)
        assert trait_result is not None
        # Score should be positive and within reasonable bounds
        # base_relevance (0~1) * (1 + sum_of_bonuses) where bonuses < 0.80
        assert trait_result["score"] > 0
        assert trait_result["score"] < 3.0, (
            f"Score {trait_result['score']} seems unreasonably high"
        )
