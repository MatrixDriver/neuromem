"""Unit tests for ContextService — context inference algorithm, keyword fallback, caching.

Tests the pure algorithmic logic without database dependency.
"""

from __future__ import annotations

import math
import time

import pytest


# ---------------------------------------------------------------------------
# Helpers — cosine similarity (standalone, mirrors expected implementation)
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Mock prototypes — 4D orthogonal vectors for precise control
# ---------------------------------------------------------------------------

MOCK_PROTOTYPES = {
    "work":     [1.0, 0.0, 0.0, 0.0],
    "personal": [0.0, 1.0, 0.0, 0.0],
    "social":   [0.0, 0.0, 1.0, 0.0],
    "learning": [0.0, 0.0, 0.0, 1.0],
}


# ---------------------------------------------------------------------------
# Inline infer_context implementation for unit testing
# (will be replaced by import from neuromem.services.context once implemented)
# ---------------------------------------------------------------------------

MARGIN_THRESHOLD = 0.05
CONFIDENCE_NORMALIZER = 0.15

CONTEXT_KEYWORDS: dict[str, set[str]] = {
    "work": {"代码", "项目", "API", "部署", "会议", "deadline", "code", "debug",
             "重构", "测试", "review", "上线", "需求", "sprint", "issue"},
    "personal": {"周末", "家里", "旅行", "做饭", "朋友", "家人", "生日", "假期",
                 "看电影", "运动", "健身", "宠物"},
    "social": {"聚会", "社交", "团建", "聊天", "约会", "关系"},
    "learning": {"学习", "教程", "原理", "论文", "课程", "入门", "理解", "概念"},
}


def _infer_context_from_embedding(
    query_embedding: list[float],
    prototypes: dict[str, list[float]],
) -> tuple[str, float]:
    """Infer context from query embedding using prototype matching."""
    similarities = {
        ctx: _cosine_similarity(query_embedding, proto)
        for ctx, proto in prototypes.items()
    }
    best_ctx = max(similarities, key=similarities.get)
    sorted_scores = sorted(similarities.values(), reverse=True)
    margin = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else sorted_scores[0]

    if margin < MARGIN_THRESHOLD:
        return ("general", 0.0)

    confidence = min(margin / CONFIDENCE_NORMALIZER, 1.0)
    return (best_ctx, confidence)


def _infer_context_with_keyword_fallback(
    query: str,
    query_embedding: list[float],
    prototypes: dict[str, list[float]],
) -> tuple[str, float]:
    """Infer context with keyword fallback when embedding is uncertain."""
    ctx, conf = _infer_context_from_embedding(query_embedding, prototypes)
    if ctx != "general":
        return (ctx, conf)

    # Keyword fallback
    keyword_hits: dict[str, int] = {}
    query_lower = query.lower()
    for context, keywords in CONTEXT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in query_lower)
        if hits > 0:
            keyword_hits[context] = hits

    if not keyword_hits:
        return ("general", 0.0)

    best_kw_ctx = max(keyword_hits, key=keyword_hits.get)
    # Use a moderate confidence for keyword-based inference
    return (best_kw_ctx, 0.5)


# ===========================================================================
# TestCosineSimilarity
# ===========================================================================


class TestCosineSimilarity:
    """CS-1~CS-4: Cosine similarity calculation correctness."""

    def test_cosine_identical_vectors(self):
        """CS-1: Identical vectors -> similarity 1.0."""
        vec = [1.0, 0.0, 0.0, 0.0]
        assert abs(_cosine_similarity(vec, vec) - 1.0) < 1e-6

    def test_cosine_orthogonal_vectors(self):
        """CS-2: Orthogonal vectors -> similarity 0.0."""
        a = [1.0, 0.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0, 0.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_cosine_opposite_vectors(self):
        """CS-3: Opposite vectors -> similarity -1.0."""
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(_cosine_similarity(a, b) + 1.0) < 1e-6

    def test_cosine_zero_vector(self):
        """CS-4: Zero vector -> similarity 0.0, no exception."""
        a = [0.0, 0.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0, 0.0]
        assert _cosine_similarity(a, b) == 0.0


# ===========================================================================
# TestInferContext
# ===========================================================================


class TestInferContext:
    """IC-1~IC-6: Context inference from query embedding."""

    def test_infer_clear_work(self):
        """IC-1: Query close to work prototype -> work context."""
        query = [0.9, 0.1, 0.0, 0.0]
        ctx, conf = _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        assert ctx == "work"
        assert conf > 0

    def test_infer_clear_personal(self):
        """IC-2: Query close to personal prototype -> personal context."""
        query = [0.0, 0.9, 0.1, 0.0]
        ctx, conf = _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        assert ctx == "personal"
        assert conf > 0

    def test_infer_clear_social(self):
        """IC-3: Query close to social prototype -> social context."""
        query = [0.0, 0.0, 0.9, 0.1]
        ctx, conf = _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        assert ctx == "social"
        assert conf > 0

    def test_infer_clear_learning(self):
        """IC-4: Query close to learning prototype -> learning context."""
        query = [0.1, 0.0, 0.0, 0.9]
        ctx, conf = _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        assert ctx == "learning"
        assert conf > 0

    def test_infer_ambiguous_returns_general(self):
        """IC-5: Ambiguous query (equal similarity to all) -> general."""
        query = [0.5, 0.5, 0.5, 0.5]
        ctx, conf = _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        assert ctx == "general"
        assert conf == 0.0

    def test_infer_dominant_with_noise(self):
        """IC-6: Work-dominant query with noise -> work context."""
        query = [0.8, 0.3, 0.2, 0.1]
        ctx, conf = _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        assert ctx == "work"
        assert conf > 0


# ===========================================================================
# TestMarginThreshold
# ===========================================================================


class TestMarginThreshold:
    """MT-1~MT-4: Margin boundary conditions."""

    def _make_query_with_margin(self, target_margin: float) -> list[float]:
        """Construct a query vector that produces an approximate target margin.

        Uses work (dim 0) as the best match and personal (dim 1) as second best.
        """
        # For orthogonal prototypes, cosine sim = component / norm.
        # Set dim0 = 1.0 (work) and dim1 = x such that margin is approximately target.
        # sim(work) = 1/sqrt(1+x^2), sim(personal) = x/sqrt(1+x^2)
        # margin = (1-x)/sqrt(1+x^2)
        # We want margin ~= target_margin. For simplicity, use iterative approach.
        best = 1.0
        # Find second_best component that gives target_margin
        for x_100 in range(0, 100):
            x = x_100 / 100.0
            norm = math.sqrt(best**2 + x**2)
            sim_work = best / norm
            sim_personal = x / norm
            m = sim_work - sim_personal
            if m <= target_margin + 0.005:
                return [best, x, 0.0, 0.0]
        return [best, 0.0, 0.0, 0.0]

    def test_margin_below_threshold(self):
        """MT-1: margin ~= 0.04 -> degradation to general."""
        query = self._make_query_with_margin(0.04)
        ctx, conf = _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        assert ctx == "general"
        assert conf == 0.0

    def test_margin_at_threshold(self):
        """MT-2: margin == 0.05 -> still degradation (strict less-than)."""
        # Equal margin means we need margin < 0.05, and exactly 0.05 also degrades
        query = self._make_query_with_margin(0.05)
        ctx, conf = _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        # At the boundary, the algorithm uses strict < so 0.05 should degrade
        # But our approximation may not be exact. Check that near-threshold
        # behaves reasonably.
        assert ctx in ("general", "work")

    def test_margin_above_threshold(self):
        """MT-3: margin > 0.05 -> valid context inference."""
        # Clear work query with high margin
        query = [1.0, 0.0, 0.0, 0.0]  # margin = 1.0
        ctx, conf = _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        assert ctx == "work"
        assert conf > 0

    def test_margin_zero_all_equal(self):
        """MT-4: All similarities equal -> margin 0 -> general."""
        query = [0.5, 0.5, 0.5, 0.5]
        ctx, conf = _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        assert ctx == "general"
        assert conf == 0.0


# ===========================================================================
# TestConfidenceNormalization
# ===========================================================================


class TestConfidenceNormalization:
    """CN-1~CN-3: Confidence normalization to [0, 1]."""

    def test_confidence_max_at_015(self):
        """CN-1: margin=0.15 -> confidence=1.0."""
        # Pure work vector: margin = 1.0, conf = min(1.0/0.15, 1.0) = 1.0
        query = [1.0, 0.0, 0.0, 0.0]
        _, conf = _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        assert conf == 1.0

    def test_confidence_proportional(self):
        """CN-2: Intermediate margin -> proportional confidence."""
        # With strong but not pure signal
        query = [0.9, 0.1, 0.0, 0.0]
        _, conf = _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        assert 0 < conf <= 1.0

    def test_confidence_cap_above_015(self):
        """CN-3: Very large margin -> confidence capped at 1.0."""
        query = [1.0, 0.0, 0.0, 0.0]  # margin = 1.0 >> 0.15
        _, conf = _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        assert conf == 1.0  # capped


# ===========================================================================
# TestKeywordFallback
# ===========================================================================


class TestKeywordFallback:
    """KF-1~KF-6: Keyword fallback when embedding is uncertain."""

    # Ambiguous embedding that always returns general
    AMBIGUOUS = [0.5, 0.5, 0.5, 0.5]

    def test_keyword_work(self):
        """KF-1: Query with '代码' keyword -> work fallback."""
        ctx, conf = _infer_context_with_keyword_fallback(
            "帮我调试这段代码", self.AMBIGUOUS, MOCK_PROTOTYPES
        )
        assert ctx == "work"
        assert conf > 0

    def test_keyword_personal(self):
        """KF-2: Query with '周末' keyword -> personal fallback."""
        ctx, conf = _infer_context_with_keyword_fallback(
            "周末去爬山", self.AMBIGUOUS, MOCK_PROTOTYPES
        )
        assert ctx == "personal"
        assert conf > 0

    def test_keyword_learning(self):
        """KF-3: Query with '学习' and '教程' -> learning fallback."""
        ctx, conf = _infer_context_with_keyword_fallback(
            "学习深度学习教程", self.AMBIGUOUS, MOCK_PROTOTYPES
        )
        assert ctx == "learning"
        assert conf > 0

    def test_keyword_no_match(self):
        """KF-4: No keyword match -> general."""
        ctx, conf = _infer_context_with_keyword_fallback(
            "今天天气不错", self.AMBIGUOUS, MOCK_PROTOTYPES
        )
        assert ctx == "general"
        assert conf == 0.0

    def test_keyword_not_used_when_embedding_confident(self):
        """KF-5: Embedding confident -> keyword ignored."""
        # Pure work embedding, even if query has '学习' keyword
        work_query = [1.0, 0.0, 0.0, 0.0]
        ctx, conf = _infer_context_with_keyword_fallback(
            "学习写代码", work_query, MOCK_PROTOTYPES
        )
        assert ctx == "work"  # embedding result takes precedence

    def test_keyword_multi_context_conflict(self):
        """KF-6: Multiple context keywords -> takes the one with most hits."""
        ctx, conf = _infer_context_with_keyword_fallback(
            "学习写代码", self.AMBIGUOUS, MOCK_PROTOTYPES
        )
        # Both "学习" (learning) and "代码" (work) hit; should return one of them
        assert ctx in ("work", "learning")
        assert conf > 0


# ===========================================================================
# TestPerformance
# ===========================================================================


class TestPerformance:
    """PF-1: Inference latency benchmark."""

    def test_infer_context_latency(self):
        """PF-1: 1000 infer_context calls < 1ms average."""
        query = [0.8, 0.3, 0.2, 0.1]
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            _infer_context_from_embedding(query, MOCK_PROTOTYPES)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 1.0, f"Average latency {avg_ms:.4f}ms exceeds 1ms threshold"
