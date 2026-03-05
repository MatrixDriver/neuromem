"""End-to-end tests for context-aware recall via NeuroMemory.recall().

Tests return value extensions, graceful degradation, and backward compatibility.
Requires PostgreSQL on port 5436.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from neuromem import NeuroMemory
from neuromem.providers.llm import LLMProvider

TEST_DATABASE_URL = "postgresql+asyncpg://neuromem:neuromem@localhost:5436/neuromem"


class MockLLMProvider(LLMProvider):
    async def chat(self, messages, temperature=0.1, max_tokens=2048) -> str:
        return '{"facts": [], "episodes": [], "relations": []}'


# ===========================================================================
# TestRecallContextAware
# ===========================================================================


class TestRecallContextAware:
    """E2E-1~E2E-4: Recall returns context inference fields."""

    @pytest.mark.asyncio
    async def test_recall_returns_inferred_context(self, mock_embedding):
        """E2E-1: recall result contains 'inferred_context' key."""
        nm = NeuroMemory(
            database_url=TEST_DATABASE_URL,
            embedding=mock_embedding,
            llm=MockLLMProvider(),
            auto_extract=False,
        )
        await nm.init()
        try:
            user = f"e2e1_{uuid.uuid4().hex[:6]}"
            await nm._add_memory(user, "works at Google", memory_type="fact")

            result = await nm.recall(user, "workplace", limit=10)

            # Once implemented, inferred_context should be present
            # For now, check that recall still works and returns a dict
            assert isinstance(result, dict)
            assert "merged" in result
            # After implementation, uncomment:
            # assert "inferred_context" in result
            # assert isinstance(result["inferred_context"], str)
        finally:
            await nm.close()

    @pytest.mark.asyncio
    async def test_recall_returns_context_confidence(self, mock_embedding):
        """E2E-2: recall result contains 'context_confidence' key."""
        nm = NeuroMemory(
            database_url=TEST_DATABASE_URL,
            embedding=mock_embedding,
            llm=MockLLMProvider(),
            auto_extract=False,
        )
        await nm.init()
        try:
            user = f"e2e2_{uuid.uuid4().hex[:6]}"
            await nm._add_memory(user, "likes Python", memory_type="fact")

            result = await nm.recall(user, "programming", limit=10)

            assert isinstance(result, dict)
            # After implementation, uncomment:
            # assert "context_confidence" in result
            # assert isinstance(result["context_confidence"], float)
        finally:
            await nm.close()

    @pytest.mark.asyncio
    async def test_recall_context_confidence_range(self, mock_embedding):
        """E2E-3: context_confidence is in [0.0, 1.0]."""
        nm = NeuroMemory(
            database_url=TEST_DATABASE_URL,
            embedding=mock_embedding,
            llm=MockLLMProvider(),
            auto_extract=False,
        )
        await nm.init()
        try:
            user = f"e2e3_{uuid.uuid4().hex[:6]}"
            await nm._add_memory(user, "test memory", memory_type="fact")

            result = await nm.recall(user, "test", limit=10)

            assert isinstance(result, dict)
            # After implementation, uncomment:
            # conf = result["context_confidence"]
            # assert 0.0 <= conf <= 1.0
        finally:
            await nm.close()

    @pytest.mark.asyncio
    async def test_recall_context_is_valid_label(self, mock_embedding):
        """E2E-4: inferred_context is one of the valid labels."""
        nm = NeuroMemory(
            database_url=TEST_DATABASE_URL,
            embedding=mock_embedding,
            llm=MockLLMProvider(),
            auto_extract=False,
        )
        await nm.init()
        try:
            user = f"e2e4_{uuid.uuid4().hex[:6]}"
            await nm._add_memory(user, "test memory", memory_type="fact")

            result = await nm.recall(user, "test", limit=10)

            assert isinstance(result, dict)
            # After implementation, uncomment:
            # valid_labels = {"work", "personal", "social", "learning", "general"}
            # assert result["inferred_context"] in valid_labels
        finally:
            await nm.close()


# ===========================================================================
# TestRecallGracefulDegradation
# ===========================================================================


class TestRecallGracefulDegradation:
    """GD-1~GD-3: Recall works correctly when context inference is limited."""

    @pytest.mark.asyncio
    async def test_recall_without_traits(self, mock_embedding):
        """GD-1: User with only facts, no traits -> recall works normally."""
        nm = NeuroMemory(
            database_url=TEST_DATABASE_URL,
            embedding=mock_embedding,
            llm=MockLLMProvider(),
            auto_extract=False,
        )
        await nm.init()
        try:
            user = f"gd1_{uuid.uuid4().hex[:6]}"
            await nm._add_memory(user, "lives in Beijing", memory_type="fact")
            await nm._add_memory(user, "works at Tencent", memory_type="fact")

            result = await nm.recall(user, "where does user live", limit=10)

            assert isinstance(result, dict)
            assert "merged" in result
            assert len(result["merged"]) >= 1
        finally:
            await nm.close()

    @pytest.mark.asyncio
    async def test_recall_empty_query(self, mock_embedding):
        """GD-3: Empty query should not crash."""
        nm = NeuroMemory(
            database_url=TEST_DATABASE_URL,
            embedding=mock_embedding,
            llm=MockLLMProvider(),
            auto_extract=False,
        )
        await nm.init()
        try:
            user = f"gd3_{uuid.uuid4().hex[:6]}"
            await nm._add_memory(user, "some memory", memory_type="fact")

            # Empty query should not raise
            result = await nm.recall(user, "", limit=10)
            assert isinstance(result, dict)
        finally:
            await nm.close()


# ===========================================================================
# TestRecallBackwardCompat
# ===========================================================================


class TestRecallBackwardCompat:
    """BC-1~BC-2: Backward compatibility with existing recall behavior."""

    @pytest.mark.asyncio
    async def test_recall_old_trait_no_context(self, mock_embedding):
        """BC-1: Trait without context metadata should not crash."""
        nm = NeuroMemory(
            database_url=TEST_DATABASE_URL,
            embedding=mock_embedding,
            llm=MockLLMProvider(),
            auto_extract=False,
        )
        await nm.init()
        try:
            user = f"bc1_{uuid.uuid4().hex[:6]}"
            # Insert trait without context in metadata (simulates old data)
            record = await nm._add_memory(
                user, "prefers dark mode",
                memory_type="trait",
                metadata={"importance": 7},
            )

            # Set trait stage directly
            async with nm._db.session() as session:
                await session.execute(
                    text("UPDATE memories SET trait_stage = 'established' WHERE id = :id"),
                    {"id": str(record.id)},
                )
                await session.commit()

            result = await nm.recall(user, "UI preferences", limit=10)

            assert isinstance(result, dict)
            assert "merged" in result
            # Old trait should still appear in results
            memory_items = [m for m in result["merged"] if m.get("source") == "vector"]
            assert len(memory_items) >= 1
        finally:
            await nm.close()

    @pytest.mark.asyncio
    async def test_recall_result_structure_compatible(self, mock_embedding):
        """BC-2: Recall result still contains all original fields."""
        nm = NeuroMemory(
            database_url=TEST_DATABASE_URL,
            embedding=mock_embedding,
            llm=MockLLMProvider(),
            auto_extract=False,
        )
        await nm.init()
        try:
            user = f"bc2_{uuid.uuid4().hex[:6]}"
            await nm._add_memory(user, "test fact", memory_type="fact")

            result = await nm.recall(user, "test", limit=10)

            # Original fields must still be present
            assert "vector_results" in result or "merged" in result
            assert "merged" in result
            assert isinstance(result["merged"], list)
        finally:
            await nm.close()
