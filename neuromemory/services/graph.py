"""Graph database service using Apache AGE."""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from sqlalchemy import delete, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from neuromemory.models.graph import EdgeType, GraphEdge, GraphNode, NodeType


class GraphService:
    """Service for managing graph data with Apache AGE."""

    def __init__(self, db: AsyncSession, user_id: Optional[str] = None):
        self.db = db
        self.user_id = user_id
        self.graph_name = "neuromemory_graph"

    def _effective_user_id(self, user_id: Optional[str] = None) -> str:
        """Resolve user_id from parameter or instance default."""
        uid = user_id or self.user_id
        if not uid:
            raise ValueError("user_id is required for graph operations")
        return uid

    async def _execute_cypher(self, cypher: str, params: dict[str, Any] = None) -> list[dict]:
        """Execute a Cypher query using AGE."""
        query = text(f"""
            SELECT * FROM ag_catalog.cypher(
                :graph_name,
                $$ {cypher} $$,
                :params
            ) as (result agtype);
        """)

        params_json = json.dumps(params or {})
        result = await self.db.execute(
            query,
            {"graph_name": self.graph_name, "params": params_json}
        )

        rows = []
        for row in result:
            rows.append(self._parse_agtype(row[0]))

        return rows

    def _parse_agtype(self, agtype_value: Any) -> dict:
        if isinstance(agtype_value, str):
            try:
                return json.loads(agtype_value)
            except json.JSONDecodeError:
                return {"value": agtype_value}
        return agtype_value

    async def create_node(
        self,
        node_type: NodeType,
        node_id: str,
        properties: dict[str, Any] = None,
        user_id: Optional[str] = None,
    ) -> GraphNode:
        """Create a node in the graph."""
        effective_user_id = self._effective_user_id(user_id)

        existing = await self.db.execute(
            select(GraphNode).where(
                GraphNode.user_id == effective_user_id,
                GraphNode.node_type == node_type.value,
                GraphNode.node_id == node_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Node {node_type.value}:{node_id} already exists")

        props = {**(properties or {}), "id": node_id, "node_type": node_type.value}

        cypher = f"CREATE (n:{node_type.value} $props) RETURN n"
        await self._execute_cypher(cypher, {"props": props})

        node = GraphNode(
            user_id=effective_user_id,
            node_type=node_type.value,
            node_id=node_id,
            properties=properties,
        )
        self.db.add(node)
        await self.db.flush()

        return node

    async def create_edge(
        self,
        source_type: NodeType,
        source_id: str,
        edge_type: EdgeType,
        target_type: NodeType,
        target_id: str,
        properties: dict[str, Any] = None,
        user_id: Optional[str] = None,
    ) -> GraphEdge:
        """Create an edge between two nodes."""
        effective_user_id = self._effective_user_id(user_id)

        for ntype, nid in [(source_type, source_id), (target_type, target_id)]:
            node = await self.db.execute(
                select(GraphNode).where(
                    GraphNode.user_id == effective_user_id,
                    GraphNode.node_type == ntype.value,
                    GraphNode.node_id == nid,
                )
            )
            if not node.scalar_one_or_none():
                raise ValueError(f"Node {ntype.value}:{nid} not found")

        props = properties or {}

        cypher = f"""
        MATCH (a:{source_type.value} {{id: $source_id}})
        MATCH (b:{target_type.value} {{id: $target_id}})
        CREATE (a)-[r:{edge_type.value} $props]->(b)
        RETURN r
        """
        params = {
            "source_id": source_id,
            "target_id": target_id,
            "props": props if props else {}
        }
        await self._execute_cypher(cypher, params)

        edge = GraphEdge(
            user_id=effective_user_id,
            source_type=source_type.value,
            source_id=source_id,
            edge_type=edge_type.value,
            target_type=target_type.value,
            target_id=target_id,
            properties=properties,
        )
        self.db.add(edge)
        await self.db.flush()

        return edge

    async def get_neighbors(
        self,
        node_type: NodeType,
        node_id: str,
        edge_types: list[EdgeType] = None,
        direction: str = "both",
        limit: int = 10,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        """Get neighboring nodes via relational tables (user-isolated)."""
        effective_user_id = self._effective_user_id(user_id)

        # Use relational tables for user-isolated neighbor queries
        conditions = [GraphEdge.user_id == effective_user_id]

        if edge_types:
            edge_type_values = [et.value for et in edge_types]
            conditions.append(GraphEdge.edge_type.in_(edge_type_values))

        results = []

        if direction in ("out", "both"):
            out_conditions = conditions + [
                GraphEdge.source_type == node_type.value,
                GraphEdge.source_id == node_id,
            ]
            out_result = await self.db.execute(
                select(GraphEdge).where(*out_conditions).limit(limit)
            )
            for edge in out_result.scalars().all():
                results.append({
                    "neighbor_type": edge.target_type,
                    "neighbor_id": edge.target_id,
                    "rel_type": edge.edge_type,
                    "rel_props": edge.properties,
                    "direction": "out",
                })

        if direction in ("in", "both"):
            remaining = limit - len(results)
            if remaining > 0:
                in_conditions = conditions + [
                    GraphEdge.target_type == node_type.value,
                    GraphEdge.target_id == node_id,
                ]
                in_result = await self.db.execute(
                    select(GraphEdge).where(*in_conditions).limit(remaining)
                )
                for edge in in_result.scalars().all():
                    results.append({
                        "neighbor_type": edge.source_type,
                        "neighbor_id": edge.source_id,
                        "rel_type": edge.edge_type,
                        "rel_props": edge.properties,
                        "direction": "in",
                    })

        return results

    async def find_path(
        self,
        source_type: NodeType,
        source_id: str,
        target_type: NodeType,
        target_id: str,
        max_depth: int = 3,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        """Find shortest path between two nodes using relational tables (user-isolated).

        Uses BFS on the relational edge table filtered by user_id.
        """
        effective_user_id = self._effective_user_id(user_id)

        if not isinstance(max_depth, int) or max_depth < 1 or max_depth > 10:
            raise ValueError("max_depth must be an integer between 1 and 10")

        # BFS on relational edges
        visited = set()
        # Queue items: (current_type, current_id, path_so_far)
        queue = [(source_type.value, source_id, [])]
        visited.add((source_type.value, source_id))

        while queue:
            current_type, current_id, path = queue.pop(0)

            if current_type == target_type.value and current_id == target_id:
                return [{"nodes": [step["node"] for step in path] + [{"type": current_type, "id": current_id}],
                         "rels": [step["edge"] for step in path]}]

            if len(path) >= max_depth:
                continue

            # Get outgoing edges
            result = await self.db.execute(
                select(GraphEdge).where(
                    GraphEdge.user_id == effective_user_id,
                    GraphEdge.source_type == current_type,
                    GraphEdge.source_id == current_id,
                )
            )
            for edge in result.scalars().all():
                neighbor_key = (edge.target_type, edge.target_id)
                if neighbor_key not in visited:
                    visited.add(neighbor_key)
                    new_path = path + [{
                        "node": {"type": current_type, "id": current_id},
                        "edge": {"type": edge.edge_type, "props": edge.properties},
                    }]
                    queue.append((edge.target_type, edge.target_id, new_path))

            # Get incoming edges
            result = await self.db.execute(
                select(GraphEdge).where(
                    GraphEdge.user_id == effective_user_id,
                    GraphEdge.target_type == current_type,
                    GraphEdge.target_id == current_id,
                )
            )
            for edge in result.scalars().all():
                neighbor_key = (edge.source_type, edge.source_id)
                if neighbor_key not in visited:
                    visited.add(neighbor_key)
                    new_path = path + [{
                        "node": {"type": current_type, "id": current_id},
                        "edge": {"type": edge.edge_type, "props": edge.properties},
                    }]
                    queue.append((edge.source_type, edge.source_id, new_path))

        return []  # No path found

    async def query(
        self,
        cypher: str,
        params: dict[str, Any] = None,
    ) -> list[dict]:
        """Execute a custom Cypher query.

        WARNING: Cypher queries bypass user isolation. Use relational
        methods (get_neighbors, find_path) for user-isolated queries.
        """
        return await self._execute_cypher(cypher, params or {})

    async def get_node(
        self,
        node_type: NodeType,
        node_id: str,
        user_id: Optional[str] = None,
    ) -> dict | None:
        """Get a single node by type and ID (user-isolated via relational table)."""
        effective_user_id = self._effective_user_id(user_id)

        result = await self.db.execute(
            select(GraphNode).where(
                GraphNode.user_id == effective_user_id,
                GraphNode.node_type == node_type.value,
                GraphNode.node_id == node_id,
            )
        )
        node = result.scalar_one_or_none()
        if not node:
            return None

        return {
            "id": str(node.id),
            "node_type": node.node_type,
            "node_id": node.node_id,
            "properties": node.properties,
            "user_id": node.user_id,
        }

    async def update_node(
        self,
        node_type: NodeType,
        node_id: str,
        properties: dict[str, Any],
        user_id: Optional[str] = None,
    ) -> GraphNode:
        """Update node properties."""
        effective_user_id = self._effective_user_id(user_id)

        node_result = await self.db.execute(
            select(GraphNode).where(
                GraphNode.user_id == effective_user_id,
                GraphNode.node_type == node_type.value,
                GraphNode.node_id == node_id,
            )
        )
        node = node_result.scalar_one_or_none()
        if not node:
            raise ValueError(f"Node {node_type.value}:{node_id} not found")

        set_clauses = ", ".join([f"n.{key} = $props.{key}" for key in properties.keys()])
        cypher = f"""
        MATCH (n:{node_type.value} {{id: $node_id}})
        SET {set_clauses}
        RETURN n
        """
        params = {
            "node_id": node_id,
            "props": properties
        }
        await self._execute_cypher(cypher, params)

        node.properties = {**(node.properties or {}), **properties}
        await self.db.flush()

        return node

    async def delete_node(
        self,
        node_type: NodeType,
        node_id: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Delete a node and all its edges."""
        effective_user_id = self._effective_user_id(user_id)

        node_result = await self.db.execute(
            select(GraphNode).where(
                GraphNode.user_id == effective_user_id,
                GraphNode.node_type == node_type.value,
                GraphNode.node_id == node_id,
            )
        )
        node = node_result.scalar_one_or_none()
        if not node:
            raise ValueError(f"Node {node_type.value}:{node_id} not found")

        cypher = f"""
        MATCH (n:{node_type.value} {{id: $node_id}})
        DETACH DELETE n
        """
        params = {"node_id": node_id}
        await self._execute_cypher(cypher, params)

        await self.db.delete(node)
        await self.db.execute(
            delete(GraphEdge).where(
                GraphEdge.user_id == effective_user_id,
                or_(
                    (GraphEdge.source_type == node_type.value) & (GraphEdge.source_id == node_id),
                    (GraphEdge.target_type == node_type.value) & (GraphEdge.target_id == node_id)
                )
            )
        )
        await self.db.flush()

    async def get_edge(
        self,
        source_type: NodeType,
        source_id: str,
        edge_type: EdgeType,
        target_type: NodeType,
        target_id: str,
        user_id: Optional[str] = None,
    ) -> dict | None:
        """Get a single edge (user-isolated via relational table)."""
        effective_user_id = self._effective_user_id(user_id)

        result = await self.db.execute(
            select(GraphEdge).where(
                GraphEdge.user_id == effective_user_id,
                GraphEdge.source_type == source_type.value,
                GraphEdge.source_id == source_id,
                GraphEdge.edge_type == edge_type.value,
                GraphEdge.target_type == target_type.value,
                GraphEdge.target_id == target_id,
            )
        )
        edge = result.scalar_one_or_none()
        if not edge:
            return None

        return {
            "id": str(edge.id),
            "source_type": edge.source_type,
            "source_id": edge.source_id,
            "edge_type": edge.edge_type,
            "target_type": edge.target_type,
            "target_id": edge.target_id,
            "properties": edge.properties,
            "user_id": edge.user_id,
        }

    async def update_edge(
        self,
        source_type: NodeType,
        source_id: str,
        edge_type: EdgeType,
        target_type: NodeType,
        target_id: str,
        properties: dict[str, Any],
        user_id: Optional[str] = None,
    ) -> GraphEdge:
        """Update edge properties."""
        effective_user_id = self._effective_user_id(user_id)

        edge_result = await self.db.execute(
            select(GraphEdge).where(
                GraphEdge.user_id == effective_user_id,
                GraphEdge.source_type == source_type.value,
                GraphEdge.source_id == source_id,
                GraphEdge.edge_type == edge_type.value,
                GraphEdge.target_type == target_type.value,
                GraphEdge.target_id == target_id,
            )
        )
        edge = edge_result.scalar_one_or_none()
        if not edge:
            raise ValueError(f"Edge {source_type.value}:{source_id}-[{edge_type.value}]->{target_type.value}:{target_id} not found")

        set_clauses = ", ".join([f"r.{key} = $props.{key}" for key in properties.keys()])
        cypher = f"""
        MATCH (a:{source_type.value} {{id: $source_id}})-[r:{edge_type.value}]->(b:{target_type.value} {{id: $target_id}})
        SET {set_clauses}
        RETURN r
        """
        params = {
            "source_id": source_id,
            "target_id": target_id,
            "props": properties
        }
        await self._execute_cypher(cypher, params)

        edge.properties = {**(edge.properties or {}), **properties}
        await self.db.flush()

        return edge

    async def delete_edge(
        self,
        source_type: NodeType,
        source_id: str,
        edge_type: EdgeType,
        target_type: NodeType,
        target_id: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Delete an edge."""
        effective_user_id = self._effective_user_id(user_id)

        edge_result = await self.db.execute(
            select(GraphEdge).where(
                GraphEdge.user_id == effective_user_id,
                GraphEdge.source_type == source_type.value,
                GraphEdge.source_id == source_id,
                GraphEdge.edge_type == edge_type.value,
                GraphEdge.target_type == target_type.value,
                GraphEdge.target_id == target_id,
            )
        )
        edge = edge_result.scalar_one_or_none()
        if not edge:
            raise ValueError(f"Edge {source_type.value}:{source_id}-[{edge_type.value}]->{target_type.value}:{target_id} not found")

        cypher = f"""
        MATCH (a:{source_type.value} {{id: $source_id}})-[r:{edge_type.value}]->(b:{target_type.value} {{id: $target_id}})
        DELETE r
        """
        params = {
            "source_id": source_id,
            "target_id": target_id,
        }
        await self._execute_cypher(cypher, params)

        await self.db.delete(edge)
        await self.db.flush()
