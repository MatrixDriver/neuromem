"""Tests for recall: three-factor scored search (relevance × recency × importance) + graph merge."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from neuromemory.services.search import DEFAULT_DECAY_RATE, SearchService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _add_memory(svc, session, user_id, content, memory_type="general",
                      metadata=None, age_days=0):
    """Add memory and optionally back-date it."""
    record = await svc.add_memory(
        user_id=user_id, content=content,
        memory_type=memory_type, metadata=metadata,
    )
    if age_days > 0:
        await session.execute(
            text("""
                UPDATE embeddings
                SET created_at = NOW() - INTERVAL ':days days'
                WHERE id = :id
            """.replace(":days", str(int(age_days)))),
            {"id": str(record.id)},
        )
    return record


async def _setup_and_search(svc, session, user_id, memories, query, **kwargs):
    """Insert multiple memories, commit, then scored_search."""
    records = []
    for m in memories:
        rec = await _add_memory(
            svc, session, user_id,
            content=m["content"],
            memory_type=m.get("memory_type", "general"),
            metadata=m.get("metadata"),
            age_days=m.get("age_days", 0),
        )
        records.append(rec)
    await session.commit()
    results = await svc.scored_search(user_id=user_id, query=query, **kwargs)
    return records, results


# ===========================================================================
# A. Recency (time decay)
# ===========================================================================

class TestRecallRecency:
    """Test exponential time decay factor."""

    @pytest.mark.asyncio
    async def test_fresh_memory_recency_near_one(self, db_session, mock_embedding):
        """A just-created memory should have recency ≈ 1.0."""
        svc = SearchService(db_session, mock_embedding)
        await svc.add_memory(user_id="recency_u1", content="fresh memory")
        await db_session.commit()

        results = await svc.scored_search(user_id="recency_u1", query="fresh memory")
        assert len(results) == 1
        assert results[0]["recency"] > 0.99

    @pytest.mark.asyncio
    async def test_old_memory_decays(self, db_session, mock_embedding):
        """A 30-day-old memory with 30-day decay rate should have recency ≈ e^-1 ≈ 0.368."""
        svc = SearchService(db_session, mock_embedding)
        await _add_memory(svc, db_session, "recency_u2", "old memory", age_days=30)
        await db_session.commit()

        results = await svc.scored_search(
            user_id="recency_u2", query="old memory",
            decay_rate=86400 * 30,
        )
        assert len(results) == 1
        # e^(-1) ≈ 0.3679
        assert 0.30 < results[0]["recency"] < 0.42

    @pytest.mark.asyncio
    async def test_very_old_memory_near_zero(self, db_session, mock_embedding):
        """A 1-year-old memory with 30-day decay should have recency near zero."""
        svc = SearchService(db_session, mock_embedding)
        await _add_memory(svc, db_session, "recency_u3", "ancient memory", age_days=365)
        await db_session.commit()

        results = await svc.scored_search(
            user_id="recency_u3", query="ancient memory",
            decay_rate=86400 * 30,
        )
        assert len(results) == 1
        # e^(-365/30) ≈ 0.000005
        assert results[0]["recency"] < 0.001

    @pytest.mark.asyncio
    async def test_fresh_beats_old_same_content(self, db_session, mock_embedding):
        """With identical content, a fresh memory should score higher than an old one."""
        svc = SearchService(db_session, mock_embedding)
        old = await _add_memory(svc, db_session, "recency_u4", "same content", age_days=60)
        fresh = await _add_memory(svc, db_session, "recency_u4", "same content", age_days=0)
        await db_session.commit()

        results = await svc.scored_search(user_id="recency_u4", query="same content")
        assert len(results) == 2
        # Fresh should rank first
        assert results[0]["id"] == str(fresh.id)
        assert results[1]["id"] == str(old.id)
        assert results[0]["score"] > results[1]["score"]

    @pytest.mark.asyncio
    async def test_decay_rate_parameter_changes_speed(self, db_session, mock_embedding):
        """Larger decay_rate makes memories fade slower."""
        svc = SearchService(db_session, mock_embedding)
        await _add_memory(svc, db_session, "recency_u5", "test decay rate", age_days=30)
        await db_session.commit()

        # Short decay: 30 days → e^(-30/30) = e^-1 ≈ 0.368
        fast = await svc.scored_search(
            user_id="recency_u5", query="test decay rate",
            decay_rate=86400 * 30,
        )
        # Long decay: 90 days → e^(-30/90) = e^-0.33 ≈ 0.717
        slow = await svc.scored_search(
            user_id="recency_u5", query="test decay rate",
            decay_rate=86400 * 90,
        )
        assert slow[0]["recency"] > fast[0]["recency"]

    @pytest.mark.asyncio
    async def test_multiple_ages_rank_by_recency(self, db_session, mock_embedding):
        """Memories at different ages should rank newest first (same content/importance)."""
        svc = SearchService(db_session, mock_embedding)
        for days in [90, 7, 30, 1]:
            await _add_memory(
                svc, db_session, "recency_u6", "identical content",
                metadata={"importance": 5}, age_days=days,
            )
        await db_session.commit()

        results = await svc.scored_search(user_id="recency_u6", query="identical content")
        recencies = [r["recency"] for r in results]
        # Should be sorted descending (freshest first)
        assert recencies == sorted(recencies, reverse=True)


# ===========================================================================
# B. Importance
# ===========================================================================

class TestRecallImportance:
    """Test importance factor (metadata.importance / 10)."""

    @pytest.mark.asyncio
    async def test_importance_scaling(self, db_session, mock_embedding):
        """Importance 1/5/10 should map to 0.1/0.5/1.0."""
        svc = SearchService(db_session, mock_embedding)
        for imp in [1, 5, 10]:
            await svc.add_memory(
                user_id="imp_u1", content=f"importance {imp}",
                metadata={"importance": imp},
            )
        await db_session.commit()

        results = await svc.scored_search(user_id="imp_u1", query="importance", limit=10)
        imp_values = sorted([r["importance"] for r in results])
        assert abs(imp_values[0] - 0.1) < 0.01
        assert abs(imp_values[1] - 0.5) < 0.01
        assert abs(imp_values[2] - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_default_importance_is_half(self, db_session, mock_embedding):
        """Memory without importance metadata should default to 0.5."""
        svc = SearchService(db_session, mock_embedding)
        await svc.add_memory(user_id="imp_u2", content="no importance set")
        await db_session.commit()

        results = await svc.scored_search(user_id="imp_u2", query="no importance set")
        assert results[0]["importance"] == 0.5

    @pytest.mark.asyncio
    async def test_high_importance_beats_low(self, db_session, mock_embedding):
        """Same content and recency: higher importance should produce higher score."""
        svc = SearchService(db_session, mock_embedding)
        await svc.add_memory(
            user_id="imp_u3", content="same text A",
            metadata={"importance": 10},
        )
        await svc.add_memory(
            user_id="imp_u3", content="same text B",
            metadata={"importance": 1},
        )
        await db_session.commit()

        results = await svc.scored_search(user_id="imp_u3", query="same text", limit=10)
        assert len(results) == 2
        # Higher importance should rank first (recency is similar for both)
        assert results[0]["importance"] > results[1]["importance"]


# ===========================================================================
# C. Arousal modifier (slows decay)
# ===========================================================================

class TestRecallArousal:
    """Test that emotional arousal slows recency decay."""

    @pytest.mark.asyncio
    async def test_high_arousal_higher_recency(self, db_session, mock_embedding):
        """High arousal memory decays slower: effective_decay = decay_rate * (1 + arousal * 0.5)."""
        svc = SearchService(db_session, mock_embedding)
        excited = await _add_memory(
            svc, db_session, "arousal_u1", "exciting event",
            metadata={"importance": 5, "emotion": {"arousal": 1.0, "valence": 0.5}},
            age_days=30,
        )
        calm = await _add_memory(
            svc, db_session, "arousal_u1", "calm event",
            metadata={"importance": 5, "emotion": {"arousal": 0.0, "valence": 0.0}},
            age_days=30,
        )
        await db_session.commit()

        results = await svc.scored_search(
            user_id="arousal_u1", query="event", decay_rate=86400 * 30,
        )
        excited_r = next(r for r in results if r["id"] == str(excited.id))
        calm_r = next(r for r in results if r["id"] == str(calm.id))

        # arousal=1.0: effective_decay = 30 * 1.5 = 45 days → e^(-30/45) ≈ 0.513
        # arousal=0.0: effective_decay = 30 * 1.0 = 30 days → e^(-30/30) ≈ 0.368
        assert excited_r["recency"] > calm_r["recency"]
        assert abs(excited_r["recency"] - 0.513) < 0.05
        assert abs(calm_r["recency"] - 0.368) < 0.05

    @pytest.mark.asyncio
    async def test_no_emotion_defaults_zero_arousal(self, db_session, mock_embedding):
        """Memory without emotion metadata should behave as arousal=0."""
        svc = SearchService(db_session, mock_embedding)
        with_emotion = await _add_memory(
            svc, db_session, "arousal_u2", "with zero arousal",
            metadata={"importance": 5, "emotion": {"arousal": 0.0}},
            age_days=10,
        )
        without_emotion = await _add_memory(
            svc, db_session, "arousal_u2", "without emotion meta",
            metadata={"importance": 5},
            age_days=10,
        )
        await db_session.commit()

        results = await svc.scored_search(user_id="arousal_u2", query="arousal")
        r_with = next(r for r in results if r["id"] == str(with_emotion.id))
        r_without = next(r for r in results if r["id"] == str(without_emotion.id))

        # Both should have same recency (arousal=0 and missing emotion are equivalent)
        assert abs(r_with["recency"] - r_without["recency"]) < 0.01


# ===========================================================================
# D. Combined scoring
# ===========================================================================

class TestRecallCombinedScoring:
    """Test the multiplication of three factors."""

    @pytest.mark.asyncio
    async def test_score_equals_product(self, db_session, mock_embedding):
        """score should equal relevance × recency × importance."""
        svc = SearchService(db_session, mock_embedding)
        await svc.add_memory(
            user_id="combo_u1", content="product test",
            metadata={"importance": 7},
        )
        await db_session.commit()

        results = await svc.scored_search(user_id="combo_u1", query="product test")
        r = results[0]
        expected = round(r["relevance"] * r["recency"] * r["importance"], 4)
        assert r["score"] == expected

    @pytest.mark.asyncio
    async def test_results_sorted_by_score_desc(self, db_session, mock_embedding):
        """Results must be ordered by score descending."""
        svc = SearchService(db_session, mock_embedding)
        for imp in [2, 8, 5, 10, 1]:
            await svc.add_memory(
                user_id="combo_u2", content=f"item {imp}",
                metadata={"importance": imp},
            )
        await db_session.commit()

        results = await svc.scored_search(user_id="combo_u2", query="item", limit=10)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_importance_can_outweigh_recency(self, db_session, mock_embedding):
        """A very important old memory can outrank a trivial fresh one."""
        svc = SearchService(db_session, mock_embedding)
        # Old but very important
        old_important = await _add_memory(
            svc, db_session, "combo_u3", "same query text",
            metadata={"importance": 10}, age_days=7,
        )
        # Fresh but trivial
        fresh_trivial = await _add_memory(
            svc, db_session, "combo_u3", "same query text",
            metadata={"importance": 1}, age_days=0,
        )
        await db_session.commit()

        results = await svc.scored_search(
            user_id="combo_u3", query="same query text",
            decay_rate=86400 * 30,
        )
        # importance 10 (1.0) vs 1 (0.1), recency ~0.79 vs ~1.0
        # old_important score ≈ rel * 0.79 * 1.0 = 0.79 * rel
        # fresh_trivial score ≈ rel * 1.0 * 0.1 = 0.1 * rel
        assert results[0]["id"] == str(old_important.id)

    @pytest.mark.asyncio
    async def test_idempotent_query(self, db_session, mock_embedding):
        """Same query twice should return same scores (excluding access_count)."""
        svc = SearchService(db_session, mock_embedding)
        await svc.add_memory(
            user_id="combo_u4", content="idempotent",
            metadata={"importance": 6},
        )
        await db_session.commit()

        r1 = await svc.scored_search(user_id="combo_u4", query="idempotent")
        r2 = await svc.scored_search(user_id="combo_u4", query="idempotent")
        # Scores should be identical (time diff is negligible within same test)
        assert abs(r1[0]["score"] - r2[0]["score"]) < 0.001


# ===========================================================================
# E. recall() facade (NeuroMemory.recall)
# ===========================================================================

class TestRecallFacade:
    """Test the NeuroMemory.recall() method (facade over scored_search + graph)."""

    @pytest.mark.asyncio
    async def test_recall_returns_correct_keys(self, nm):
        """recall() should return vector_results, graph_results, merged."""
        await nm.add_memory(user_id="facade_u1", content="facade test")
        result = await nm.recall(user_id="facade_u1", query="facade test")

        assert "vector_results" in result
        assert "graph_results" in result
        assert "merged" in result

    @pytest.mark.asyncio
    async def test_recall_merged_has_source_tag(self, nm):
        """Each item in merged should have a 'source' field."""
        await nm.add_memory(user_id="facade_u2", content="source tag test")
        result = await nm.recall(user_id="facade_u2", query="source tag test")

        assert len(result["merged"]) > 0
        for item in result["merged"]:
            assert "source" in item
            assert item["source"] in ("vector", "graph")

    @pytest.mark.asyncio
    async def test_recall_merged_deduplicates(self, nm):
        """Duplicate content should appear only once in merged."""
        await nm.add_memory(user_id="facade_u3", content="duplicate content A")
        await nm.add_memory(user_id="facade_u3", content="duplicate content A")
        result = await nm.recall(user_id="facade_u3", query="duplicate content A")

        contents = [m["content"] for m in result["merged"]]
        assert len(contents) == len(set(contents))

    @pytest.mark.asyncio
    async def test_recall_respects_limit(self, nm):
        """merged should not exceed the requested limit."""
        for i in range(20):
            await nm.add_memory(user_id="facade_u4", content=f"memory number {i}")

        result = await nm.recall(user_id="facade_u4", query="memory number", limit=5)
        assert len(result["merged"]) <= 5

    @pytest.mark.asyncio
    async def test_recall_user_isolation(self, nm):
        """recall() should only return memories of the queried user."""
        await nm.add_memory(user_id="user_x", content="secret of X")
        await nm.add_memory(user_id="user_y", content="secret of Y")

        result = await nm.recall(user_id="user_x", query="secret")
        for item in result["merged"]:
            assert "X" in item["content"]

    @pytest.mark.asyncio
    async def test_recall_empty_results(self, nm):
        """recall() on a user with no memories should return empty lists."""
        result = await nm.recall(user_id="nonexistent_user", query="anything")
        assert result["vector_results"] == []
        assert result["graph_results"] == []
        assert result["merged"] == []

    @pytest.mark.asyncio
    async def test_recall_custom_decay_rate(self, nm):
        """Custom decay_rate should be passed through to scored_search."""
        await nm.add_memory(
            user_id="facade_u5", content="decay rate test",
            metadata={"importance": 5},
        )

        # Very large decay rate → recency stays close to 1.0
        result = await nm.recall(
            user_id="facade_u5", query="decay rate test",
            decay_rate=86400 * 365,  # 1-year decay
        )
        assert len(result["merged"]) > 0
        assert result["vector_results"][0]["recency"] > 0.99

    @pytest.mark.asyncio
    async def test_recall_default_decay_rate(self, nm):
        """Without decay_rate, should use DEFAULT_DECAY_RATE (30 days)."""
        await nm.add_memory(
            user_id="facade_u6", content="default decay",
            metadata={"importance": 5},
        )

        result = await nm.recall(user_id="facade_u6", query="default decay")
        # Fresh memory → recency near 1.0 regardless of decay_rate
        assert result["vector_results"][0]["recency"] > 0.99


# ===========================================================================
# F. Edge cases
# ===========================================================================

class TestRecallEdgeCases:
    """Boundary conditions and special cases."""

    @pytest.mark.asyncio
    async def test_single_memory(self, db_session, mock_embedding):
        """Should work with only one memory in the database."""
        svc = SearchService(db_session, mock_embedding)
        await svc.add_memory(user_id="edge_u1", content="only one")
        await db_session.commit()

        results = await svc.scored_search(user_id="edge_u1", query="only one")
        assert len(results) == 1
        assert results[0]["score"] > 0

    @pytest.mark.asyncio
    async def test_limit_one(self, db_session, mock_embedding):
        """limit=1 should return exactly one result."""
        svc = SearchService(db_session, mock_embedding)
        for i in range(5):
            await svc.add_memory(user_id="edge_u2", content=f"entry {i}")
        await db_session.commit()

        results = await svc.scored_search(user_id="edge_u2", query="entry", limit=1)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_memory_type_filter(self, db_session, mock_embedding):
        """scored_search with memory_type filter should only return matching type."""
        svc = SearchService(db_session, mock_embedding)
        await svc.add_memory(
            user_id="edge_u3", content="this is a fact",
            memory_type="fact", metadata={"importance": 5},
        )
        await svc.add_memory(
            user_id="edge_u3", content="this is episodic",
            memory_type="episodic", metadata={"importance": 5},
        )
        await db_session.commit()

        results = await svc.scored_search(
            user_id="edge_u3", query="this is",
            memory_type="fact",
        )
        assert all(r["memory_type"] == "fact" for r in results)

    @pytest.mark.asyncio
    async def test_metadata_preserved_in_results(self, db_session, mock_embedding):
        """Full metadata object should be returned in results."""
        svc = SearchService(db_session, mock_embedding)
        meta = {
            "importance": 8,
            "emotion": {"valence": -0.5, "arousal": 0.7, "label": "anxious"},
            "custom_field": "custom_value",
        }
        await svc.add_memory(
            user_id="edge_u4", content="metadata check",
            metadata=meta,
        )
        await db_session.commit()

        results = await svc.scored_search(user_id="edge_u4", query="metadata check")
        assert results[0]["metadata"]["emotion"]["label"] == "anxious"
        assert results[0]["metadata"]["custom_field"] == "custom_value"

    @pytest.mark.asyncio
    async def test_all_scores_non_negative(self, db_session, mock_embedding):
        """All factor scores should be >= 0."""
        svc = SearchService(db_session, mock_embedding)
        await svc.add_memory(
            user_id="edge_u5", content="non negative check",
            metadata={"importance": 1},
        )
        await db_session.commit()

        results = await svc.scored_search(user_id="edge_u5", query="non negative check")
        for r in results:
            assert r["relevance"] >= 0
            assert r["recency"] >= 0
            assert r["importance"] >= 0
            assert r["score"] >= 0

    @pytest.mark.asyncio
    async def test_access_tracking_increments(self, db_session, mock_embedding):
        """Multiple scored_search calls should increment access_count."""
        svc = SearchService(db_session, mock_embedding)
        record = await svc.add_memory(
            user_id="edge_u6", content="access tracking test",
        )
        await db_session.commit()

        # Search three times
        for _ in range(3):
            await svc.scored_search(user_id="edge_u6", query="access tracking test")

        result = await db_session.execute(
            text("SELECT access_count, last_accessed_at FROM embeddings WHERE id = :id"),
            {"id": str(record.id)},
        )
        row = result.fetchone()
        assert row.access_count == 3
        assert row.last_accessed_at is not None
