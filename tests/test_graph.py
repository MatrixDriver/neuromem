"""Tests for graph service.

These tests use mocked AGE functionality since AGE requires specific
database configuration.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from neuromemory.models.graph import EdgeType, NodeType
from neuromemory.services.graph import GraphService

TEST_USER_ID = "test-user-123"


@pytest.mark.asyncio
async def test_create_node(db_session):
    """Test creating a graph node."""
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{"id": "user123"}]

        svc = GraphService(db_session, user_id=TEST_USER_ID)
        node = await svc.create_node(
            node_type=NodeType.USER,
            node_id="user123",
            properties={"name": "Alice"},
        )

        assert node.node_type == "User"
        assert node.node_id == "user123"
        assert node.user_id == TEST_USER_ID
        assert node.properties == {"name": "Alice"}
        mock_cypher.assert_called_once()


@pytest.mark.asyncio
async def test_create_node_duplicate(db_session):
    """Test creating a duplicate node raises error."""
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{}]

        svc = GraphService(db_session, user_id=TEST_USER_ID)
        await svc.create_node(node_type=NodeType.USER, node_id="dup_user")
        await db_session.flush()

        with pytest.raises(ValueError, match="already exists"):
            await svc.create_node(node_type=NodeType.USER, node_id="dup_user")


@pytest.mark.asyncio
async def test_create_node_requires_user_id(db_session):
    """Test that user_id is required for node creation."""
    svc = GraphService(db_session)  # No user_id

    with pytest.raises(ValueError, match="user_id is required"):
        await svc.create_node(node_type=NodeType.USER, node_id="user1")


@pytest.mark.asyncio
async def test_create_edge(db_session):
    """Test creating a graph edge."""
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{}]

        svc = GraphService(db_session, user_id=TEST_USER_ID)
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
        assert edge.user_id == TEST_USER_ID


@pytest.mark.asyncio
async def test_create_edge_missing_node(db_session):
    """Test creating edge when node doesn't exist."""
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock):
        svc = GraphService(db_session, user_id=TEST_USER_ID)

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
    """Test getting neighbors via relational tables."""
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{}]

        svc = GraphService(db_session, user_id=TEST_USER_ID)
        # Create nodes and edge
        await svc.create_node(node_type=NodeType.USER, node_id="user123")
        await svc.create_node(node_type=NodeType.MEMORY, node_id="mem1")
        await svc.create_node(node_type=NodeType.MEMORY, node_id="mem2")
        await db_session.flush()

        await svc.create_edge(
            source_type=NodeType.USER, source_id="user123",
            edge_type=EdgeType.HAS_MEMORY,
            target_type=NodeType.MEMORY, target_id="mem1",
        )
        await svc.create_edge(
            source_type=NodeType.USER, source_id="user123",
            edge_type=EdgeType.HAS_MEMORY,
            target_type=NodeType.MEMORY, target_id="mem2",
        )
        await db_session.flush()

        results = await svc.get_neighbors(
            node_type=NodeType.USER,
            node_id="user123",
            edge_types=[EdgeType.HAS_MEMORY],
            direction="out",
        )

        assert len(results) == 2
        assert all(r["rel_type"] == "HAS_MEMORY" for r in results)


@pytest.mark.asyncio
async def test_get_neighbors_user_isolation(db_session):
    """Test that get_neighbors only returns edges for the requesting user."""
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{}]

        # User A creates nodes and edge
        svc_a = GraphService(db_session, user_id="user-a")
        await svc_a.create_node(node_type=NodeType.USER, node_id="alice")
        await svc_a.create_node(node_type=NodeType.CONCEPT, node_id="python")
        await db_session.flush()
        await svc_a.create_edge(
            source_type=NodeType.USER, source_id="alice",
            edge_type=EdgeType.HAS_SKILL,
            target_type=NodeType.CONCEPT, target_id="python",
        )
        await db_session.flush()

        # User B creates nodes with same IDs
        svc_b = GraphService(db_session, user_id="user-b")
        await svc_b.create_node(node_type=NodeType.USER, node_id="alice")
        await db_session.flush()

        # User B should see no neighbors for "alice"
        results = await svc_b.get_neighbors(
            node_type=NodeType.USER, node_id="alice", direction="out",
        )
        assert len(results) == 0

        # User A should see the neighbor
        results = await svc_a.get_neighbors(
            node_type=NodeType.USER, node_id="alice", direction="out",
        )
        assert len(results) == 1


@pytest.mark.asyncio
async def test_find_path(db_session):
    """Test finding path via relational tables."""
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{}]

        svc = GraphService(db_session, user_id=TEST_USER_ID)
        await svc.create_node(node_type=NodeType.USER, node_id="user123")
        await svc.create_node(node_type=NodeType.MEMORY, node_id="mem456")
        await db_session.flush()
        await svc.create_edge(
            source_type=NodeType.USER, source_id="user123",
            edge_type=EdgeType.HAS_MEMORY,
            target_type=NodeType.MEMORY, target_id="mem456",
        )
        await db_session.flush()

        results = await svc.find_path(
            source_type=NodeType.USER,
            source_id="user123",
            target_type=NodeType.MEMORY,
            target_id="mem456",
            max_depth=3,
        )

        assert len(results) == 1
        assert len(results[0]["nodes"]) == 2


@pytest.mark.asyncio
async def test_find_path_invalid_depth(db_session):
    svc = GraphService(db_session, user_id=TEST_USER_ID)
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

        svc = GraphService(db_session, user_id=TEST_USER_ID)
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
    svc = GraphService(db_session, user_id=TEST_USER_ID)
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

        svc = GraphService(db_session, user_id=TEST_USER_ID)
        await svc.create_node(node_type=NodeType.USER, node_id="del_user")
        await db_session.flush()

        await svc.delete_node(node_type=NodeType.USER, node_id="del_user")
        # Should not raise


@pytest.mark.asyncio
async def test_delete_node_not_found(db_session):
    svc = GraphService(db_session, user_id=TEST_USER_ID)
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


@pytest.mark.asyncio
async def test_get_node(db_session):
    """Test getting a node by type and ID."""
    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{}]

        svc = GraphService(db_session, user_id=TEST_USER_ID)
        await svc.create_node(node_type=NodeType.USER, node_id="get_user", properties={"name": "Test"})
        await db_session.flush()

        result = await svc.get_node(node_type=NodeType.USER, node_id="get_user")
        assert result is not None
        assert result["node_id"] == "get_user"
        assert result["user_id"] == TEST_USER_ID

        # Different user should not see this node
        svc2 = GraphService(db_session, user_id="other-user")
        result2 = await svc2.get_node(node_type=NodeType.USER, node_id="get_user")
        assert result2 is None
