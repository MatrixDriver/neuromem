"""Tests for memory extraction with LLM classifier."""

import pytest
from unittest.mock import AsyncMock, patch

from neuromemory.providers.llm import LLMProvider
from neuromemory.services.conversation import ConversationService
from neuromemory.services.graph import GraphService
from neuromemory.services.memory_extraction import MemoryExtractionService
from neuromemory.services.kv import KVService


class MockLLMProvider(LLMProvider):
    """Mock LLM that returns predictable classification results."""

    def __init__(self, response: str = ""):
        self._response = response

    async def chat(self, messages, temperature=0.1, max_tokens=2048) -> str:
        return self._response


@pytest.mark.asyncio
async def test_extract_memories_from_conversations(db_session, mock_embedding):
    """Test extracting memories from conversation messages."""
    # Add conversation messages
    conv_svc = ConversationService(db_session)
    _, msg_ids = await conv_svc.add_messages_batch(
        user_id="test_user",
        messages=[
            {"role": "user", "content": "我在 Google 工作，主要做后端开发"},
            {"role": "assistant", "content": "很高兴认识您！"},
            {"role": "user", "content": "我喜欢蓝色，平时喜欢看科幻电影"},
            {"role": "assistant", "content": "了解了您的偏好！"},
        ],
    )

    # Get messages for extraction
    messages = await conv_svc.get_unextracted_messages(user_id="test_user")

    # Mock LLM response
    mock_llm = MockLLMProvider(response="""```json
{
  "preferences": [
    {"key": "favorite_color", "value": "蓝色", "confidence": 0.95},
    {"key": "hobby", "value": "看科幻电影", "confidence": 0.90}
  ],
  "facts": [
    {"content": "在 Google 工作", "category": "work", "confidence": 0.98},
    {"content": "主要做后端开发", "category": "skill", "confidence": 0.95}
  ],
  "episodes": []
}
```""")

    extraction_svc = MemoryExtractionService(db_session, mock_embedding, mock_llm)
    result = await extraction_svc.extract_from_messages(
        user_id="test_user",
        messages=messages,
    )

    assert result["messages_processed"] == 4
    assert result["preferences_extracted"] == 2
    assert result["facts_extracted"] == 2
    assert result["episodes_extracted"] == 0

    # Verify preferences stored via KV
    kv_svc = KVService(db_session)
    items = await kv_svc.list("preferences", "test_user")
    assert len(items) >= 2


@pytest.mark.asyncio
async def test_extract_with_no_messages(db_session, mock_embedding):
    """Test extraction when there are no messages."""
    mock_llm = MockLLMProvider()
    extraction_svc = MemoryExtractionService(db_session, mock_embedding, mock_llm)
    result = await extraction_svc.extract_from_messages(
        user_id="nonexistent_user",
        messages=[],
    )

    assert result["messages_processed"] == 0
    assert result["preferences_extracted"] == 0


@pytest.mark.asyncio
async def test_parse_classification_result():
    """Test classifier JSON parsing with various formats."""
    mock_llm = MockLLMProvider()
    svc = MemoryExtractionService.__new__(MemoryExtractionService)

    # With markdown code block
    result1 = svc._parse_classification_result("""
```json
{
  "preferences": [{"key": "color", "value": "blue", "confidence": 0.9}],
  "facts": [],
  "episodes": []
}
```
    """)
    assert len(result1["preferences"]) == 1
    assert result1["preferences"][0]["key"] == "color"

    # Without markdown
    result2 = svc._parse_classification_result("""
{
  "preferences": [],
  "facts": [{"content": "test", "category": "work", "confidence": 0.8}],
  "episodes": []
}
    """)
    assert len(result2["facts"]) == 1

    # Invalid JSON
    result3 = svc._parse_classification_result("not json")
    assert result3 == {"preferences": [], "facts": [], "episodes": [], "triples": []}


@pytest.mark.asyncio
async def test_extract_with_graph_triples(db_session, mock_embedding):
    """Test extraction with graph_enabled=True stores triples."""
    conv_svc = ConversationService(db_session)
    _, msg_ids = await conv_svc.add_messages_batch(
        user_id="test_user",
        messages=[
            {"role": "user", "content": "我在 Google 工作，主要做后端开发"},
            {"role": "assistant", "content": "很高兴认识您！"},
        ],
    )
    messages = await conv_svc.get_unextracted_messages(user_id="test_user")

    mock_llm = MockLLMProvider(response="""```json
{
  "preferences": [],
  "facts": [
    {"content": "在 Google 工作", "category": "work", "confidence": 0.98}
  ],
  "episodes": [],
  "triples": [
    {"subject": "user", "subject_type": "user", "relation": "works_at",
     "object": "Google", "object_type": "organization",
     "content": "在 Google 工作", "confidence": 0.98},
    {"subject": "user", "subject_type": "user", "relation": "has_skill",
     "object": "后端开发", "object_type": "skill",
     "content": "主要做后端开发", "confidence": 0.95}
  ]
}
```""")

    with patch.object(GraphService, "_execute_cypher", new_callable=AsyncMock) as mock_cypher:
        mock_cypher.return_value = [{}]

        extraction_svc = MemoryExtractionService(
            db_session, mock_embedding, mock_llm, graph_enabled=True,
        )
        result = await extraction_svc.extract_from_messages(
            user_id="test_user",
            messages=messages,
        )

    assert result["facts_extracted"] == 1
    assert result["triples_extracted"] == 2
    assert result["messages_processed"] == 2


@pytest.mark.asyncio
async def test_extract_without_graph_ignores_triples(db_session, mock_embedding):
    """Test extraction with graph_enabled=False does not store triples."""
    conv_svc = ConversationService(db_session)
    _, _ = await conv_svc.add_messages_batch(
        user_id="test_user2",
        messages=[
            {"role": "user", "content": "我在 Google 工作"},
        ],
    )
    messages = await conv_svc.get_unextracted_messages(user_id="test_user2")

    mock_llm = MockLLMProvider(response="""```json
{
  "preferences": [],
  "facts": [{"content": "在 Google 工作", "category": "work", "confidence": 0.98}],
  "episodes": [],
  "triples": [
    {"subject": "user", "subject_type": "user", "relation": "works_at",
     "object": "Google", "object_type": "organization",
     "content": "在 Google 工作", "confidence": 0.98}
  ]
}
```""")

    extraction_svc = MemoryExtractionService(
        db_session, mock_embedding, mock_llm, graph_enabled=False,
    )
    result = await extraction_svc.extract_from_messages(
        user_id="test_user2",
        messages=messages,
    )

    assert result["facts_extracted"] == 1
    assert result["triples_extracted"] == 0  # graph disabled


@pytest.mark.asyncio
async def test_parse_classification_with_triples():
    """Test parser handles triples field."""
    svc = MemoryExtractionService.__new__(MemoryExtractionService)

    result = svc._parse_classification_result("""```json
{
  "preferences": [],
  "facts": [{"content": "在 Google 工作", "category": "work", "confidence": 0.98}],
  "episodes": [],
  "triples": [
    {"subject": "user", "subject_type": "user", "relation": "works_at",
     "object": "Google", "object_type": "organization",
     "content": "在 Google 工作", "confidence": 0.98}
  ]
}
```""")
    assert len(result["triples"]) == 1
    assert result["triples"][0]["relation"] == "works_at"


@pytest.mark.asyncio
async def test_extract_with_emotion_and_importance(db_session, mock_embedding):
    """Test extraction stores emotion and importance in metadata."""
    from sqlalchemy import text

    conv_svc = ConversationService(db_session)
    _, _ = await conv_svc.add_messages_batch(
        user_id="emotion_user",
        messages=[
            {"role": "user", "content": "今天被裁员了，很难过"},
            {"role": "assistant", "content": "很抱歉听到这个消息"},
        ],
    )
    messages = await conv_svc.get_unextracted_messages(user_id="emotion_user")

    mock_llm = MockLLMProvider(response="""```json
{
  "preferences": [],
  "facts": [
    {
      "content": "被公司裁员",
      "category": "work",
      "confidence": 0.95,
      "importance": 9,
      "emotion": {"valence": -0.8, "arousal": 0.7, "label": "悲伤"}
    }
  ],
  "episodes": [
    {
      "content": "今天被裁员了",
      "timestamp": null,
      "confidence": 0.95,
      "importance": 9,
      "emotion": {"valence": -0.8, "arousal": 0.7, "label": "悲伤"}
    }
  ]
}
```""")

    extraction_svc = MemoryExtractionService(db_session, mock_embedding, mock_llm)
    result = await extraction_svc.extract_from_messages(
        user_id="emotion_user", messages=messages,
    )

    assert result["facts_extracted"] == 1
    assert result["episodes_extracted"] == 1

    # Verify metadata in DB
    rows = await db_session.execute(
        text("SELECT metadata FROM embeddings WHERE user_id = :uid"),
        {"uid": "emotion_user"},
    )
    for row in rows.fetchall():
        meta = row.metadata
        assert meta["importance"] == 9
        assert meta["emotion"]["valence"] == -0.8
        assert meta["emotion"]["arousal"] == 0.7
        assert meta["emotion"]["label"] == "悲伤"


@pytest.mark.asyncio
async def test_extract_without_emotion_backward_compatible(db_session, mock_embedding):
    """Test that extraction works without emotion fields (backward compatibility)."""
    conv_svc = ConversationService(db_session)
    _, _ = await conv_svc.add_messages_batch(
        user_id="compat_user",
        messages=[{"role": "user", "content": "我喜欢编程"}],
    )
    messages = await conv_svc.get_unextracted_messages(user_id="compat_user")

    # LLM response without emotion/importance (old format)
    mock_llm = MockLLMProvider(response="""```json
{
  "preferences": [],
  "facts": [
    {"content": "喜欢编程", "category": "hobby", "confidence": 0.9}
  ],
  "episodes": []
}
```""")

    extraction_svc = MemoryExtractionService(db_session, mock_embedding, mock_llm)
    result = await extraction_svc.extract_from_messages(
        user_id="compat_user", messages=messages,
    )

    assert result["facts_extracted"] == 1
