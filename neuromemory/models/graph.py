"""Graph data models for Apache AGE integration."""

import uuid
from enum import Enum

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from neuromemory.models.base import Base, TimestampMixin


class NodeType(str, Enum):
    USER = "User"
    MEMORY = "Memory"
    CONCEPT = "Concept"
    ENTITY = "Entity"
    ORGANIZATION = "Organization"
    LOCATION = "Location"
    SKILL = "Skill"


class EdgeType(str, Enum):
    HAS_MEMORY = "HAS_MEMORY"
    MENTIONS = "MENTIONS"
    RELATED_TO = "RELATED_TO"
    KNOWS = "KNOWS"
    ABOUT = "ABOUT"
    WORKS_AT = "WORKS_AT"
    LIVES_IN = "LIVES_IN"
    HAS_SKILL = "HAS_SKILL"
    STUDIED_AT = "STUDIED_AT"
    BELONGS_TO = "BELONGS_TO"
    USES = "USES"
    CUSTOM = "CUSTOM"


class GraphNode(Base, TimestampMixin):
    """Graph node tracking table (actual graph data in AGE)."""

    __tablename__ = "graph_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    node_id: Mapped[str] = mapped_column(String(255), nullable=False)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_graph_nodes_lookup", "node_type", "node_id", unique=True),
    )


class GraphEdge(Base, TimestampMixin):
    """Graph edge tracking table (actual graph data in AGE)."""

    __tablename__ = "graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    edge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index(
            "ix_graph_edges_lookup",
            "source_type", "source_id",
            "edge_type",
            "target_type", "target_id",
        ),
    )
