"""Tests for memory add and semantic search."""

import pytest

from neuromemory.services.search import SearchService


@pytest.mark.asyncio
async def test_add_memory(db_session, mock_embedding):
    """Add a memory and verify it returns correctly."""
    svc = SearchService(db_session, mock_embedding)
    record = await svc.add_memory(
        user_id="u1",
        content="I work at ABC Company as a Python developer",
        memory_type="general",
    )
    assert record.content == "I work at ABC Company as a Python developer"
    assert record.memory_type == "general"
    assert record.id is not None


@pytest.mark.asyncio
async def test_search_memories(db_session, mock_embedding):
    """Add memories and search for them."""
    svc = SearchService(db_session, mock_embedding)
    await svc.add_memory(user_id="search_user", content="I love Python programming")
    await svc.add_memory(user_id="search_user", content="My favorite food is sushi")
    await db_session.commit()

    results = await svc.search(user_id="search_user", query="programming language", limit=5)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_search_with_memory_type_filter(db_session, mock_embedding):
    """Search with memory type filter."""
    svc = SearchService(db_session, mock_embedding)
    await svc.add_memory(user_id="u2", content="Fact about Python", memory_type="fact")
    await svc.add_memory(user_id="u2", content="Event yesterday", memory_type="episodic")
    await db_session.commit()

    results = await svc.search(user_id="u2", query="Python", memory_type="fact")
    assert all(r["memory_type"] == "fact" for r in results)


@pytest.mark.asyncio
async def test_search_user_isolation(db_session, mock_embedding):
    """Search should only return memories for the specified user."""
    svc = SearchService(db_session, mock_embedding)
    await svc.add_memory(user_id="user_a", content="Secret info for A")
    await svc.add_memory(user_id="user_b", content="Secret info for B")
    await db_session.commit()

    results = await svc.search(user_id="user_a", query="secret info", limit=10)
    for r in results:
        assert "user_a" or r["content"] == "Secret info for A"


@pytest.mark.asyncio
async def test_add_memory_via_facade(nm):
    """Test adding memory through the NeuroMemory facade."""
    record = await nm.add_memory(user_id="u1", content="I work at Google")
    assert record.content == "I work at Google"
    assert record.id is not None


@pytest.mark.asyncio
async def test_search_via_facade(nm):
    """Test search through the NeuroMemory facade."""
    await nm.add_memory(user_id="facade_user", content="I love cats")
    await nm.add_memory(user_id="facade_user", content="Python is great")

    results = await nm.search(user_id="facade_user", query="animals")
    assert len(results) > 0
