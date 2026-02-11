"""Tests for graph service.

These tests use mocked AGE functionality since AGE requires specific
database configuration.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from neuromemory.models.graph import EdgeType, NodeType
from neuromemory.services.graph import GraphService


@pytest.mark.asyncio
async def test_create_node(db_session):
    """Test creating a graph node."""
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{"id": "user123"}]

        svc = GraphService(db_session)
        node = await svc.create_node(
            node_type=NodeType.USER,
            node_id="user123",
            properties={"name": "Alice"},
        )

        assert node.node_type == "User"
        assert node.node_id == "user123"
        assert node.properties == {"name": "Alice"}
        mock_cypher.assert_called_once()


@pytest.mark.asyncio
async def test_create_node_duplicate(db_session):
    """Test creating a duplicate node raises error."""
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{}]

        svc = GraphService(db_session)
        await svc.create_node(node_type=NodeType.USER, node_id="dup_user")
        await db_session.flush()

        with pytest.raises(ValueError, match="already exists"):
            await svc.create_node(node_type=NodeType.USER, node_id="dup_user")


@pytest.mark.asyncio
async def test_create_edge(db_session):
    """Test creating a graph edge."""
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{}]

        svc = GraphService(db_session)
        # Create source and target nodes first
        await svc.create_node(node_type=NodeType.USER, node_id="user1")
        await svc.create_node(node_type=NodeType.MEMORY, node_id="mem1")
        await db_session.flush()

        edge = await svc.create_edge(
            source_type=NodeType.USER,
            source_id="user1",
            edge_type=EdgeType.HAS_MEMORY,
            target_type=NodeType.MEMORY,
            target_id="mem1",
            properties={"weight": 1.0},
        )

        assert edge.source_type == "User"
        assert edge.source_id == "user1"
        assert edge.edge_type == "HAS_MEMORY"
        assert edge.target_type == "Memory"
        assert edge.target_id == "mem1"


@pytest.mark.asyncio
async def test_create_edge_missing_node(db_session):
    """Test creating edge when node doesn't exist."""
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock):
        svc = GraphService(db_session)

        with pytest.raises(ValueError, match="not found"):
            await svc.create_edge(
                source_type=NodeType.USER,
                source_id="nonexistent",
                edge_type=EdgeType.HAS_MEMORY,
                target_type=NodeType.MEMORY,
                target_id="mem1",
            )


@pytest.mark.asyncio
async def test_get_neighbors(db_session):
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [
            {"neighbor": {"id": "mem1"}, "rel_type": "HAS_MEMORY", "rel_props": {}},
            {"neighbor": {"id": "mem2"}, "rel_type": "HAS_MEMORY", "rel_props": {}},
        ]

        svc = GraphService(db_session)
        results = await svc.get_neighbors(
            node_type=NodeType.USER,
            node_id="user123",
            edge_types=[EdgeType.HAS_MEMORY],
            direction="out",
        )

        assert len(results) == 2
        mock_cypher.assert_called_once()


@pytest.mark.asyncio
async def test_find_path(db_session):
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [
            {"nodes": [{"id": "user123"}, {"id": "mem456"}], "rels": [{"type": "HAS_MEMORY"}]}
        ]

        svc = GraphService(db_session)
        results = await svc.find_path(
            source_type=NodeType.USER,
            source_id="user123",
            target_type=NodeType.MEMORY,
            target_id="mem456",
            max_depth=3,
        )

        assert len(results) == 1


@pytest.mark.asyncio
async def test_find_path_invalid_depth(db_session):
    svc = GraphService(db_session)
    with pytest.raises(ValueError, match="max_depth"):
        await svc.find_path(
            source_type=NodeType.USER,
            source_id="u1",
            target_type=NodeType.MEMORY,
            target_id="m1",
            max_depth=11,
        )


@pytest.mark.asyncio
async def test_update_node(db_session):
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{}]

        svc = GraphService(db_session)
        await svc.create_node(node_type=NodeType.USER, node_id="upd_user", properties={"name": "Alice"})
        await db_session.flush()

        node = await svc.update_node(
            node_type=NodeType.USER,
            node_id="upd_user",
            properties={"email": "alice@example.com"},
        )

        assert node.properties["email"] == "alice@example.com"
        assert node.properties["name"] == "Alice"


@pytest.mark.asyncio
async def test_update_node_not_found(db_session):
    svc = GraphService(db_session)
    with pytest.raises(ValueError, match="not found"):
        await svc.update_node(
            node_type=NodeType.USER,
            node_id="nonexistent",
            properties={"name": "Bob"},
        )


@pytest.mark.asyncio
async def test_delete_node(db_session):
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{}]

        svc = GraphService(db_session)
        await svc.create_node(node_type=NodeType.USER, node_id="del_user")
        await db_session.flush()

        await svc.delete_node(node_type=NodeType.USER, node_id="del_user")
        # Should not raise


@pytest.mark.asyncio
async def test_delete_node_not_found(db_session):
    svc = GraphService(db_session)
    with pytest.raises(ValueError, match="not found"):
        await svc.delete_node(node_type=NodeType.USER, node_id="nonexistent")


@pytest.mark.asyncio
async def test_custom_query(db_session):
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [
            {"user_id": "u1", "count": 5},
        ]

        svc = GraphService(db_session)
        results = await svc.query(
            cypher="MATCH (u:User)-[:HAS_MEMORY]->(m) RETURN u.id, count(m)",
        )

        assert len(results) == 1
        assert results[0]["count"] == 5
