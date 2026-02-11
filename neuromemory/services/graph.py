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
        effective_user_id = user_id or self.user_id

        existing = await self.db.execute(
            select(GraphNode).where(
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
        effective_user_id = user_id or self.user_id

        for ntype, nid in [(source_type, source_id), (target_type, target_id)]:
            node = await self.db.execute(
                select(GraphNode).where(
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
    ) -> list[dict]:
        """Get neighboring nodes."""
        edge_filter = ""
        if edge_types:
            edge_types_str = "|".join([et.value for et in edge_types])
            edge_filter = f":{edge_types_str}"

        if direction == "out":
            rel = f"-[r{edge_filter}]->"
        elif direction == "in":
            rel = f"<-[r{edge_filter}]-"
        else:
            rel = f"-[r{edge_filter}]-"

        cypher = f"""
        MATCH (n:{node_type.value} {{id: $node_id}})
        {rel}(neighbor)
        RETURN neighbor, type(r) as rel_type, properties(r) as rel_props
        LIMIT $limit
        """
        params = {
            "node_id": node_id,
            "limit": limit
        }

        return await self._execute_cypher(cypher, params)

    async def find_path(
        self,
        source_type: NodeType,
        source_id: str,
        target_type: NodeType,
        target_id: str,
        max_depth: int = 3,
    ) -> list[dict]:
        """Find shortest path between two nodes."""
        if not isinstance(max_depth, int) or max_depth < 1 or max_depth > 10:
            raise ValueError("max_depth must be an integer between 1 and 10")

        cypher = f"""
        MATCH path = shortestPath(
            (a:{source_type.value} {{id: $source_id}})-[*..{max_depth}]-
            (b:{target_type.value} {{id: $target_id}})
        )
        RETURN nodes(path) as nodes, relationships(path) as rels
        """
        params = {
            "source_id": source_id,
            "target_id": target_id,
        }

        return await self._execute_cypher(cypher, params)

    async def query(
        self,
        cypher: str,
        params: dict[str, Any] = None,
    ) -> list[dict]:
        """Execute a custom Cypher query."""
        return await self._execute_cypher(cypher, params or {})

    async def get_node(
        self,
        node_type: NodeType,
        node_id: str,
    ) -> dict | None:
        """Get a single node by type and ID."""
        cypher = f"""
        MATCH (n:{node_type.value} {{id: $node_id}})
        RETURN n
        """
        params = {"node_id": node_id}

        results = await self._execute_cypher(cypher, params)
        return results[0] if results else None

    async def update_node(
        self,
        node_type: NodeType,
        node_id: str,
        properties: dict[str, Any],
    ) -> GraphNode:
        """Update node properties."""
        node_result = await self.db.execute(
            select(GraphNode).where(
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
    ) -> None:
        """Delete a node and all its edges."""
        node_result = await self.db.execute(
            select(GraphNode).where(
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
    ) -> dict | None:
        """Get a single edge."""
        cypher = f"""
        MATCH (a:{source_type.value} {{id: $source_id}})-[r:{edge_type.value}]->(b:{target_type.value} {{id: $target_id}})
        RETURN r
        """
        params = {
            "source_id": source_id,
            "target_id": target_id,
        }

        results = await self._execute_cypher(cypher, params)
        return results[0] if results else None

    async def update_edge(
        self,
        source_type: NodeType,
        source_id: str,
        edge_type: EdgeType,
        target_type: NodeType,
        target_id: str,
        properties: dict[str, Any],
    ) -> GraphEdge:
        """Update edge properties."""
        edge_result = await self.db.execute(
            select(GraphEdge).where(
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
    ) -> None:
        """Delete an edge."""
        edge_result = await self.db.execute(
            select(GraphEdge).where(
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
