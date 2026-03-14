"""Tests for trait feedback mechanism."""
import pytest
from neuromem.services.memory import MemoryService
from neuromem.services.search import SearchService


@pytest.fixture
async def setup_trait(db_session, mock_embedding):
    """Create a trait memory for testing."""
    svc = SearchService(db_session, mock_embedding)
    await svc.add_memory(
        "test_fb_user", "User tends to work late at night",
        memory_type="trait",
        metadata={"trait_stage": "trend", "trait_confidence": 0.5,
                  "trait_reinforcement_count": 0, "trait_contradiction_count": 0},
    )
    await db_session.commit()
    # Get the trait ID
    from neuromem.models.memory import Memory
    from sqlalchemy import select
    result = await db_session.execute(
        select(Memory).where(Memory.user_id == "test_fb_user", Memory.memory_type == "trait")
    )
    trait = result.scalar_one()
    return str(trait.id)


class TestTraitFeedback:
    @pytest.mark.asyncio
    async def test_useful_feedback_boosts_confidence(self, db_session, mock_embedding, setup_trait):
        svc = MemoryService(db_session)
        result = await svc.feedback_trait(setup_trait, "test_fb_user", useful=True)
        assert result is not None
        assert result["useful"] is True
        assert result["reinforcement_count"] == 1
        assert result["confidence"] == 0.55  # 0.5 + 0.05

    @pytest.mark.asyncio
    async def test_not_useful_reduces_confidence(self, db_session, mock_embedding, setup_trait):
        svc = MemoryService(db_session)
        result = await svc.feedback_trait(setup_trait, "test_fb_user", useful=False)
        assert result is not None
        assert result["useful"] is False
        assert result["contradiction_count"] == 1
        assert result["confidence"] == 0.45  # 0.5 - 0.05

    @pytest.mark.asyncio
    async def test_confidence_capped_at_1(self, db_session, mock_embedding, setup_trait):
        svc = MemoryService(db_session)
        # Boost 12 times: 0.5 + 12*0.05 = 1.1 -> capped at 1.0
        for _ in range(12):
            result = await svc.feedback_trait(setup_trait, "test_fb_user", useful=True)
        assert result["confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_confidence_floor_at_0(self, db_session, mock_embedding, setup_trait):
        svc = MemoryService(db_session)
        # Reduce 12 times: 0.5 - 12*0.05 = -0.1 -> floored at 0.0
        for _ in range(12):
            result = await svc.feedback_trait(setup_trait, "test_fb_user", useful=False)
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_nonexistent_trait_returns_none(self, db_session):
        svc = MemoryService(db_session)
        result = await svc.feedback_trait("00000000-0000-0000-0000-000000000000", "nobody", useful=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_wrong_user_returns_none(self, db_session, mock_embedding, setup_trait):
        svc = MemoryService(db_session)
        result = await svc.feedback_trait(setup_trait, "wrong_user", useful=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_non_trait_memory_returns_none(self, db_session, mock_embedding):
        """Feedback only works on trait-type memories."""
        svc = SearchService(db_session, mock_embedding)
        await svc.add_memory("test_fb_user2", "A fact", memory_type="fact")
        await db_session.commit()
        from neuromem.models.memory import Memory
        from sqlalchemy import select
        result = await db_session.execute(
            select(Memory).where(Memory.user_id == "test_fb_user2", Memory.memory_type == "fact")
        )
        fact = result.scalar_one()

        mem_svc = MemoryService(db_session)
        result = await mem_svc.feedback_trait(str(fact.id), "test_fb_user2", useful=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_multiple_feedbacks_accumulate(self, db_session, mock_embedding, setup_trait):
        svc = MemoryService(db_session)
        await svc.feedback_trait(setup_trait, "test_fb_user", useful=True)
        await svc.feedback_trait(setup_trait, "test_fb_user", useful=True)
        result = await svc.feedback_trait(setup_trait, "test_fb_user", useful=False)
        assert result["reinforcement_count"] == 2
        assert result["contradiction_count"] == 1
        # confidence: 0.5 + 0.05 + 0.05 - 0.05 = 0.55
        assert result["confidence"] == 0.55
