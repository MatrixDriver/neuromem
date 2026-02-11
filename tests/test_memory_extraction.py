"""Tests for memory extraction with LLM classifier."""

import pytest
from unittest.mock import AsyncMock

from neuromemory.providers.llm import LLMProvider
from neuromemory.services.conversation import ConversationService
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
    assert result3 == {"preferences": [], "facts": [], "episodes": []}
