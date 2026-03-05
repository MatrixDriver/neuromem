"""Integration tests for ContextService — uses actual imports from neuromem."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from neuromem.services.context import ContextService, cosine_similarity


# ---------------------------------------------------------------------------
# Unit tests: cosine_similarity
# ---------------------------------------------------------------------------


class TestCosineFunction:
    def test_identical(self):
        v = [1.0, 2.0, 3.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal(self):
        assert abs(cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-6

    def test_zero_vector(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


# ---------------------------------------------------------------------------
# Unit tests: ContextService with injected prototypes
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx_svc():
    svc = ContextService(MagicMock())
    svc._prototypes = {
        "work": [1.0, 0.0, 0.0, 0.0],
        "personal": [0.0, 1.0, 0.0, 0.0],
        "social": [0.0, 0.0, 1.0, 0.0],
        "learning": [0.0, 0.0, 0.0, 1.0],
    }
    svc._prototype_norms = {ctx: 1.0 for ctx in svc._prototypes}
    return svc


class TestInferContext:
    def test_clear_match(self, ctx_svc):
        ctx, conf = ctx_svc.infer_context([1.0, 0.0, 0.0, 0.0])
        assert ctx == "work"
        assert conf > 0

    def test_ambiguous(self, ctx_svc):
        ctx, conf = ctx_svc.infer_context([0.5, 0.5, 0.5, 0.5])
        assert ctx == "general"
        assert conf == 0.0

    def test_no_prototypes(self):
        svc = ContextService(MagicMock())
        ctx, conf = svc.infer_context([1.0, 0.0, 0.0])
        assert ctx == "general"
        assert conf == 0.0

    def test_zero_query(self, ctx_svc):
        ctx, conf = ctx_svc.infer_context([0.0, 0.0, 0.0, 0.0])
        assert ctx == "general"
        assert conf == 0.0


class TestKeywordFallback:
    def test_work_keywords(self, ctx_svc):
        result = ctx_svc._infer_context_keywords("帮我调试这个 bug，代码有问题")
        assert result is not None
        assert result[0] == "work"

    def test_no_match(self, ctx_svc):
        result = ctx_svc._infer_context_keywords("今天感觉还不错")
        assert result is None

    def test_ambiguous_triggers_keyword(self, ctx_svc):
        ctx, conf = ctx_svc.infer_context([0.5, 0.5, 0.5, 0.5], query_text="帮我调试这个 bug，代码有问题")
        assert ctx == "work"
        assert conf > 0


# ---------------------------------------------------------------------------
# Integration tests: ensure_prototypes lazy load
# ---------------------------------------------------------------------------


@pytest.mark.requires_db
async def test_ensure_prototypes_lazy_load(nm):
    svc = ContextService(nm._embedding)
    assert svc._prototypes is None
    await svc.ensure_prototypes()
    assert svc._prototypes is not None
    assert len(svc._prototypes) == 4
    first_ref = svc._prototypes
    await svc.ensure_prototypes()
    assert svc._prototypes is first_ref


# ---------------------------------------------------------------------------
# Integration tests: recall returns context fields
# ---------------------------------------------------------------------------


@pytest.mark.requires_db
async def test_recall_returns_context_fields(nm):
    user_id = "test_context_user"
    await nm.ingest(user_id=user_id, role="user", content="I prefer functional programming")
    import asyncio
    await asyncio.sleep(0.5)

    result = await nm.recall(user_id=user_id, query="help me write code")
    assert "inferred_context" in result
    assert "context_confidence" in result
    assert isinstance(result["inferred_context"], str)
    assert isinstance(result["context_confidence"], float)
    assert result["context_confidence"] >= 0.0
    assert result["context_confidence"] <= 1.0


@pytest.mark.requires_db
async def test_recall_context_match_in_scores(nm):
    user_id = "test_context_score_user"
    await nm.ingest(user_id=user_id, role="user", content="I like using Python for data analysis at work")
    import asyncio
    await asyncio.sleep(0.5)

    result = await nm.recall(user_id=user_id, query="help me write Python code")
    for r in result.get("vector_results", []):
        assert "context_match" in r
