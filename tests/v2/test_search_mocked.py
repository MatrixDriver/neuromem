"""Tests for memory add and semantic search with mocked embedding service.

These tests use mocked embeddings to avoid requiring a real API key.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_add_memory_mocked(client):
    """Add a memory with mocked embedding service."""
    # Mock the embedding service
    mock_embedding = [0.1] * 1024  # 1024-dimensional mock vector

    with patch("server.app.services.embedding.EmbeddingService.embed") as mock_embed:
        mock_embed.return_value = mock_embedding

        resp = await client.post(
            "/v1/memories",
            json={
                "user_id": "u1",
                "content": "I work at ABC Company as a Python developer",
                "memory_type": "general",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "I work at ABC Company as a Python developer"
        assert data["memory_type"] == "general"
        assert "id" in data

        # Verify embedding service was called
        mock_embed.assert_called_once_with(
            "I work at ABC Company as a Python developer"
        )


@pytest.mark.asyncio
async def test_search_memories_mocked(client):
    """Search memories with mocked embedding service."""
    # Mock embeddings for both add and search
    mock_embedding_python = [0.9, 0.8] + [0.1] * 1022  # High similarity to Python
    mock_embedding_food = [0.1, 0.2] + [0.1] * 1022  # Low similarity to Python
    mock_embedding_query = [0.85, 0.75] + [0.1] * 1022  # Similar to Python

    with patch("server.app.services.embedding.EmbeddingService.embed") as mock_embed:
        # Setup mock to return different embeddings for different inputs
        def mock_embed_side_effect(text):
            if "Python" in text or "programming" in text:
                return mock_embedding_python
            elif "sushi" in text or "food" in text:
                return mock_embedding_food
            else:
                return mock_embedding_query

        mock_embed.side_effect = mock_embed_side_effect

        # Add some memories
        await client.post(
            "/v1/memories",
            json={"user_id": "search_user", "content": "I love Python programming"},
        )
        await client.post(
            "/v1/memories",
            json={"user_id": "search_user", "content": "My favorite food is sushi"},
        )

        # Search
        resp = await client.post(
            "/v1/search",
            json={
                "user_id": "search_user",
                "query": "programming language",
                "limit": 5,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) > 0

        # First result should be about Python (more relevant based on our mock)
        assert "Python" in data["results"][0]["content"]

        # Verify embedding service was called
        assert mock_embed.call_count >= 3  # 2 adds + 1 search


@pytest.mark.asyncio
async def test_add_memory_handles_embedding_error(client):
    """Test that adding memory handles embedding service errors gracefully."""
    with patch("server.app.services.embedding.EmbeddingService.embed") as mock_embed:
        # Simulate embedding service failure
        mock_embed.side_effect = Exception("Embedding service unavailable")

        resp = await client.post(
            "/v1/memories",
            json={
                "user_id": "u1",
                "content": "Test content",
            },
        )

        # Should return 500 error
        assert resp.status_code == 500
        data = resp.json()
        assert "Failed to add memory" in data["detail"]


@pytest.mark.asyncio
async def test_search_handles_embedding_error(client):
    """Test that search handles embedding service errors gracefully."""
    with patch("server.app.services.embedding.EmbeddingService.embed") as mock_embed:
        # Simulate embedding service failure
        mock_embed.side_effect = Exception("Embedding service unavailable")

        resp = await client.post(
            "/v1/search",
            json={
                "user_id": "u1",
                "query": "test query",
            },
        )

        # Should return 500 error
        assert resp.status_code == 500
        data = resp.json()
        assert "Search failed" in data["detail"]


@pytest.mark.asyncio
async def test_add_memory_with_metadata_mocked(client):
    """Add a memory with metadata using mocked embedding."""
    mock_embedding = [0.1] * 1024

    with patch("server.app.services.embedding.EmbeddingService.embed") as mock_embed:
        mock_embed.return_value = mock_embedding

        resp = await client.post(
            "/v1/memories",
            json={
                "user_id": "u1",
                "content": "Completed Python course on 2024-01-15",
                "memory_type": "event",
                "metadata": {"category": "education", "date": "2024-01-15"},
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "Completed Python course on 2024-01-15"
        assert data["memory_type"] == "event"
        assert data["metadata"]["category"] == "education"
        assert data["metadata"]["date"] == "2024-01-15"
