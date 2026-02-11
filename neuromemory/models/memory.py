"""Memory embedding model."""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

import neuromemory.models as _models
from neuromemory.models.base import Base, TimestampMixin


class Embedding(Base, TimestampMixin):
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(
        Vector(None), nullable=False
    )
    memory_type: Mapped[str] = mapped_column(
        String(50), default="general"
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("ix_emb_user", "user_id"),
    )

    @classmethod
    def __declare_last__(cls):
        """Set vector dimension from runtime config after all models declared."""
        cls.__table__.c.embedding.type = Vector(_models._embedding_dims)
