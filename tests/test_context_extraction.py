"""Tests for context labeling during memory extraction.

Covers:
- TS-2.1: Normal context labeling for fact/episodic
- TS-2.2: Fallback/degradation for invalid/missing context
- TS-2.3: Whitelist validation
- EI-*: Integration tests for context storage

Requires PostgreSQL on port 5436 for integration tests.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from neuromem.providers.llm import LLMProvider
from neuromem.services.conversation import ConversationService
from neuromem.services.memory_extraction import MemoryExtractionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_CONTEXTS = {"work", "personal", "social", "learning", "general"}


class MockLLMWithContext(LLMProvider):
    """Mock LLM that returns extraction results with context field."""

    def __init__(self, response: str):
        self._response = response

    async def chat(self, messages, temperature=0.1, max_tokens=2048) -> str:
        return self._response


def _make_fact_response(content: str, context: str | None = None, **kwargs) -> str:
    """Build a mock LLM JSON response with a single fact."""
    fact: dict = {"content": content, "confidence": 0.9, "importance": 7}
    if context is not None:
        fact["context"] = context
    fact.update(kwargs)
    import json
    return json.dumps({"facts": [fact], "episodes": [], "triples": []})


def _make_episode_response(content: str, context: str | None = None) -> str:
    """Build a mock LLM JSON response with a single episode."""
    episode: dict = {"content": content, "confidence": 0.9}
    if context is not None:
        episode["context"] = context
    import json
    return json.dumps({"facts": [], "episodes": [episode], "triples": []})


# ===========================================================================
# TestContextWhitelist (TS-2.3)
# ===========================================================================


class TestContextWhitelist:
    """EX-10: Validate the context whitelist."""

    def test_whitelist_completeness(self):
        """EX-10: Whitelist contains exactly 5 valid labels."""
        assert VALID_CONTEXTS == {"work", "personal", "social", "learning", "general"}

    def test_whitelist_all_lowercase(self):
        """All whitelist values should be lowercase."""
        for ctx in VALID_CONTEXTS:
            assert ctx == ctx.lower()


# ===========================================================================
# TestContextValidation — unit tests for validation logic
# ===========================================================================


def _validate_context(value: str | None) -> str:
    """Validate and normalize context value. Mirrors expected implementation."""
    if not value or value not in VALID_CONTEXTS:
        return "general"
    return value


class TestContextValidation:
    """EX-3 ~ EX-9: Context validation/fallback logic."""

    def test_valid_work(self):
        assert _validate_context("work") == "work"

    def test_valid_personal(self):
        assert _validate_context("personal") == "personal"

    def test_valid_social(self):
        assert _validate_context("social") == "social"

    def test_valid_learning(self):
        assert _validate_context("learning") == "learning"

    def test_valid_general(self):
        assert _validate_context("general") == "general"

    def test_invalid_health(self):
        """EX-6: Invalid value 'health' -> general."""
        assert _validate_context("health") == "general"

    def test_invalid_finance(self):
        assert _validate_context("finance") == "general"

    def test_empty_string(self):
        """EX-8: Empty string -> general."""
        assert _validate_context("") == "general"

    def test_none(self):
        """EX-9: None -> general."""
        assert _validate_context(None) == "general"

    def test_uppercase_work(self):
        """Case sensitivity: 'Work' is not in whitelist -> general."""
        assert _validate_context("Work") == "general"


# ===========================================================================
# Integration tests: extraction stores context (requires DB)
# ===========================================================================


@pytest.mark.asyncio
async def test_store_fact_with_work_context(db_session, mock_embedding):
    """EI-1 / EX-1: ingest fact with context='work' -> trait_context stored."""
    uid = f"ctx_fact_{uuid.uuid4().hex[:6]}"
    llm = MockLLMWithContext(_make_fact_response("works at Google", context="work"))
    svc = MemoryExtractionService(db_session, mock_embedding, llm)

    conv_svc = ConversationService(db_session)
    _, msg_ids = await conv_svc.add_messages_batch(
        user_id=uid,
        messages=[
            {"role": "user", "content": "I work at Google"},
            {"role": "assistant", "content": "Nice!"},
        ],
    )
    messages = await conv_svc.get_unextracted_messages(user_id=uid)

    result = await svc.extract_from_messages(uid, messages)
    assert result["facts_extracted"] >= 1

    # Verify trait_context in database
    row = (await db_session.execute(
        text("SELECT trait_context FROM memories WHERE user_id = :uid AND memory_type = 'fact' LIMIT 1"),
        {"uid": uid},
    )).fetchone()
    assert row is not None
    assert row.trait_context == "work"


@pytest.mark.asyncio
async def test_store_episodic_with_learning_context(db_session, mock_embedding):
    """EI-2 / EX-2: ingest episodic with context='learning' -> trait_context stored."""
    uid = f"ctx_ep_{uuid.uuid4().hex[:6]}"
    llm = MockLLMWithContext(_make_episode_response("studied Transformer paper", context="learning"))
    svc = MemoryExtractionService(db_session, mock_embedding, llm)

    conv_svc = ConversationService(db_session)
    _, msg_ids = await conv_svc.add_messages_batch(
        user_id=uid,
        messages=[
            {"role": "user", "content": "Today I read the Transformer paper"},
            {"role": "assistant", "content": "Great!"},
        ],
    )
    messages = await conv_svc.get_unextracted_messages(user_id=uid)

    result = await svc.extract_from_messages(uid, messages)
    assert result["episodes_extracted"] >= 1

    row = (await db_session.execute(
        text("SELECT trait_context FROM memories WHERE user_id = :uid AND memory_type = 'episodic' LIMIT 1"),
        {"uid": uid},
    )).fetchone()
    assert row is not None
    assert row.trait_context == "learning"


@pytest.mark.asyncio
async def test_store_fact_invalid_context_fallback(db_session, mock_embedding):
    """EI-3 / EX-6: invalid context 'health' -> falls back to 'general'."""
    uid = f"ctx_inv_{uuid.uuid4().hex[:6]}"
    llm = MockLLMWithContext(_make_fact_response("exercises daily", context="health"))
    svc = MemoryExtractionService(db_session, mock_embedding, llm)

    conv_svc = ConversationService(db_session)
    _, _ = await conv_svc.add_messages_batch(
        user_id=uid,
        messages=[
            {"role": "user", "content": "I exercise every day"},
            {"role": "assistant", "content": "Healthy!"},
        ],
    )
    messages = await conv_svc.get_unextracted_messages(user_id=uid)

    result = await svc.extract_from_messages(uid, messages)
    assert result["facts_extracted"] >= 1

    row = (await db_session.execute(
        text("SELECT trait_context FROM memories WHERE user_id = :uid AND memory_type = 'fact' LIMIT 1"),
        {"uid": uid},
    )).fetchone()
    assert row is not None
    assert row.trait_context == "general"


@pytest.mark.asyncio
async def test_store_fact_missing_context_fallback(db_session, mock_embedding):
    """EX-7: missing context field -> falls back to 'general'."""
    uid = f"ctx_miss_{uuid.uuid4().hex[:6]}"
    # _make_fact_response with context=None omits the field
    llm = MockLLMWithContext(_make_fact_response("likes Python"))
    svc = MemoryExtractionService(db_session, mock_embedding, llm)

    conv_svc = ConversationService(db_session)
    _, _ = await conv_svc.add_messages_batch(
        user_id=uid,
        messages=[
            {"role": "user", "content": "I like Python"},
            {"role": "assistant", "content": "Cool!"},
        ],
    )
    messages = await conv_svc.get_unextracted_messages(user_id=uid)

    result = await svc.extract_from_messages(uid, messages)
    assert result["facts_extracted"] >= 1

    row = (await db_session.execute(
        text("SELECT trait_context FROM memories WHERE user_id = :uid AND memory_type = 'fact' LIMIT 1"),
        {"uid": uid},
    )).fetchone()
    assert row is not None
    assert row.trait_context == "general"
