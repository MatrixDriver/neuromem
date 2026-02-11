"""NeuroMemory main class (facade pattern)."""

from __future__ import annotations

from typing import Optional

from neuromemory.db import Database
from neuromemory.providers.embedding import EmbeddingProvider
from neuromemory.providers.llm import LLMProvider
from neuromemory.storage.base import ObjectStorage


class KVFacade:
    """Key-value storage facade."""

    def __init__(self, db: Database):
        self._db = db

    async def set(self, namespace: str, scope_id: str, key: str, value):
        from neuromemory.services.kv import KVService
        async with self._db.session() as session:
            svc = KVService(session)
            return await svc.set(namespace, scope_id, key, value)

    async def get(self, namespace: str, scope_id: str, key: str):
        from neuromemory.services.kv import KVService
        async with self._db.session() as session:
            svc = KVService(session)
            return await svc.get(namespace, scope_id, key)

    async def list(self, namespace: str, scope_id: str, prefix: str | None = None, limit: int = 100):
        from neuromemory.services.kv import KVService
        async with self._db.session() as session:
            svc = KVService(session)
            return await svc.list(namespace, scope_id, prefix, limit)

    async def delete(self, namespace: str, scope_id: str, key: str) -> bool:
        from neuromemory.services.kv import KVService
        async with self._db.session() as session:
            svc = KVService(session)
            return await svc.delete(namespace, scope_id, key)

    async def batch_set(self, namespace: str, scope_id: str, items: dict):
        from neuromemory.services.kv import KVService
        async with self._db.session() as session:
            svc = KVService(session)
            return await svc.batch_set(namespace, scope_id, items)


class ConversationsFacade:
    """Conversations facade."""

    def __init__(self, db: Database):
        self._db = db

    async def add_message(self, user_id: str, role: str, content: str, session_id: str | None = None, metadata: dict | None = None):
        from neuromemory.services.conversation import ConversationService
        async with self._db.session() as session:
            svc = ConversationService(session)
            return await svc.add_message(user_id, role, content, session_id, metadata)

    async def add_messages_batch(self, user_id: str, messages: list[dict], session_id: str | None = None):
        from neuromemory.services.conversation import ConversationService
        async with self._db.session() as session:
            svc = ConversationService(session)
            return await svc.add_messages_batch(user_id, messages, session_id)

    async def get_session_messages(self, user_id: str, session_id: str, limit: int = 100, offset: int = 0):
        from neuromemory.services.conversation import ConversationService
        async with self._db.session() as session:
            svc = ConversationService(session)
            return await svc.get_session_messages(user_id, session_id, limit, offset)

    async def list_sessions(self, user_id: str, limit: int = 50, offset: int = 0):
        from neuromemory.services.conversation import ConversationService
        async with self._db.session() as session:
            svc = ConversationService(session)
            return await svc.list_sessions(user_id, limit, offset)

    async def get_unextracted_messages(self, user_id: str, session_id: str | None = None, limit: int = 100):
        from neuromemory.services.conversation import ConversationService
        async with self._db.session() as session:
            svc = ConversationService(session)
            return await svc.get_unextracted_messages(user_id, session_id, limit)


class FilesFacade:
    """Files facade."""

    def __init__(self, db: Database, embedding: EmbeddingProvider, storage: ObjectStorage):
        self._db = db
        self._embedding = embedding
        self._storage = storage

    async def upload(self, user_id: str, filename: str, file_data: bytes, category: str = "general", tags: list[str] | None = None, metadata: dict | None = None):
        from neuromemory.services.files import FileService
        async with self._db.session() as session:
            svc = FileService(session, self._embedding, self._storage)
            return await svc.upload(user_id, filename, file_data, category, tags, metadata)

    async def create_from_text(self, user_id: str, title: str, content: str, category: str = "general", tags: list[str] | None = None, metadata: dict | None = None):
        from neuromemory.services.files import FileService
        async with self._db.session() as session:
            svc = FileService(session, self._embedding, self._storage)
            return await svc.create_from_text(user_id, title, content, category, tags, metadata)

    async def list(self, user_id: str, category: str | None = None, tags: list[str] | None = None, file_types: list[str] | None = None, limit: int = 50):
        from neuromemory.services.files import FileService
        async with self._db.session() as session:
            svc = FileService(session, self._embedding, self._storage)
            return await svc.list_documents(user_id, category, tags, file_types, limit)

    async def get(self, file_id):
        from neuromemory.services.files import FileService
        async with self._db.session() as session:
            svc = FileService(session, self._embedding, self._storage)
            return await svc.get_document(file_id)

    async def delete(self, file_id) -> bool:
        from neuromemory.services.files import FileService
        async with self._db.session() as session:
            svc = FileService(session, self._embedding, self._storage)
            return await svc.delete_document(file_id)


class GraphFacade:
    """Graph facade."""

    def __init__(self, db: Database):
        self._db = db

    async def create_node(self, node_type, node_id: str, properties: dict | None = None, user_id: str | None = None):
        from neuromemory.services.graph import GraphService
        async with self._db.session() as session:
            svc = GraphService(session)
            return await svc.create_node(node_type, node_id, properties, user_id)

    async def get_node(self, node_type, node_id: str):
        from neuromemory.services.graph import GraphService
        async with self._db.session() as session:
            svc = GraphService(session)
            return await svc.get_node(node_type, node_id)

    async def update_node(self, node_type, node_id: str, properties: dict):
        from neuromemory.services.graph import GraphService
        async with self._db.session() as session:
            svc = GraphService(session)
            return await svc.update_node(node_type, node_id, properties)

    async def delete_node(self, node_type, node_id: str):
        from neuromemory.services.graph import GraphService
        async with self._db.session() as session:
            svc = GraphService(session)
            return await svc.delete_node(node_type, node_id)

    async def create_edge(self, source_type, source_id: str, edge_type, target_type, target_id: str, properties: dict | None = None, user_id: str | None = None):
        from neuromemory.services.graph import GraphService
        async with self._db.session() as session:
            svc = GraphService(session)
            return await svc.create_edge(source_type, source_id, edge_type, target_type, target_id, properties, user_id)

    async def get_neighbors(self, node_type, node_id: str, edge_types=None, direction: str = "both", limit: int = 10):
        from neuromemory.services.graph import GraphService
        async with self._db.session() as session:
            svc = GraphService(session)
            return await svc.get_neighbors(node_type, node_id, edge_types, direction, limit)

    async def find_path(self, source_type, source_id: str, target_type, target_id: str, max_depth: int = 3):
        from neuromemory.services.graph import GraphService
        async with self._db.session() as session:
            svc = GraphService(session)
            return await svc.find_path(source_type, source_id, target_type, target_id, max_depth)

    async def query(self, cypher: str, params: dict | None = None):
        from neuromemory.services.graph import GraphService
        async with self._db.session() as session:
            svc = GraphService(session)
            return await svc.query(cypher, params)


class NeuroMemory:
    """Main NeuroMemory facade - entry point for all operations.

    Usage:
        nm = NeuroMemory(
            database_url="postgresql+asyncpg://...",
            embedding=SiliconFlowEmbedding(api_key="..."),
        )
        await nm.init()

        await nm.add_memory(user_id="u1", content="I work at Google")
        results = await nm.search(user_id="u1", query="workplace")

        await nm.close()

    Or as async context manager:
        async with NeuroMemory(...) as nm:
            await nm.search(...)
    """

    def __init__(
        self,
        database_url: str,
        embedding: EmbeddingProvider,
        llm: Optional[LLMProvider] = None,
        storage: Optional[ObjectStorage] = None,
        pool_size: int = 10,
        echo: bool = False,
    ):
        # Set embedding dimensions before any model import
        import neuromemory.models as _models
        _models._embedding_dims = embedding.dims

        self._db = Database(database_url, pool_size=pool_size, echo=echo)
        self._embedding = embedding
        self._llm = llm
        self._storage = storage

        # Sub-module facades
        self.kv = KVFacade(self._db)
        self.conversations = ConversationsFacade(self._db)
        self.graph = GraphFacade(self._db)

        if storage:
            self.files = FilesFacade(self._db, self._embedding, storage)

    async def init(self) -> None:
        """Initialize database tables and optional storage."""
        await self._db.init()
        if self._storage:
            await self._storage.init()

    async def close(self) -> None:
        """Close database connections."""
        await self._db.close()

    async def __aenter__(self) -> "NeuroMemory":
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    # -- Top-level convenience methods --

    async def add_memory(
        self,
        user_id: str,
        content: str,
        memory_type: str = "general",
        metadata: dict | None = None,
    ):
        """Add a memory with auto-generated embedding."""
        from neuromemory.services.search import SearchService
        async with self._db.session() as session:
            svc = SearchService(session, self._embedding)
            return await svc.add_memory(user_id, content, memory_type, metadata)

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        memory_type: str | None = None,
        created_after=None,
        created_before=None,
    ) -> list[dict]:
        """Semantic search for memories."""
        from neuromemory.services.search import SearchService
        async with self._db.session() as session:
            svc = SearchService(session, self._embedding)
            return await svc.search(user_id, query, limit, memory_type, created_after, created_before)

    async def get_memories_by_time_range(self, user_id: str, start_time, end_time=None, memory_type=None, limit=100, offset=0):
        from neuromemory.services.memory import MemoryService
        async with self._db.session() as session:
            svc = MemoryService(session)
            return await svc.get_memories_by_time_range(user_id, start_time, end_time, memory_type, limit, offset)

    async def get_recent_memories(self, user_id: str, days: int = 7, memory_types=None, limit: int = 50):
        from neuromemory.services.memory import MemoryService
        async with self._db.session() as session:
            svc = MemoryService(session)
            return await svc.get_recent_memories(user_id, days, memory_types, limit)

    async def extract_memories(self, user_id: str, messages):
        """Extract memories from conversation messages using LLM."""
        if not self._llm:
            raise RuntimeError("LLM provider required for memory extraction")
        from neuromemory.services.memory_extraction import MemoryExtractionService
        async with self._db.session() as session:
            svc = MemoryExtractionService(session, self._embedding, self._llm)
            return await svc.extract_from_messages(user_id, messages)
