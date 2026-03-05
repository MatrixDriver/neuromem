"""Unit tests for MRR (Mean Reciprocal Rank) calculation and parameter evaluation.

Tests the evaluation script's core logic without database dependency.
Corresponds to test spec TS-1 (MRR-1 ~ MRR-6, PARAM-1 ~ PARAM-2).
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Inline MRR implementation (will be imported from scripts/ once implemented)
# ---------------------------------------------------------------------------


def compute_mrr(results: list[str], ground_truth: str | list[str], k: int | None = None) -> float:
    """Compute Reciprocal Rank for a single query.

    Args:
        results: Ranked list of result IDs.
        ground_truth: Expected ID(s).  If a list, any match counts.
        k: Optional top-k cutoff.
    """
    if not results:
        return 0.0
    expected = {ground_truth} if isinstance(ground_truth, str) else set(ground_truth)
    search_list = results[:k] if k else results
    for i, rid in enumerate(search_list):
        if rid in expected:
            return 1.0 / (i + 1)
    return 0.0


def compute_mean_mrr(
    queries: list[dict],
    k: int | None = None,
) -> float:
    """Compute Mean Reciprocal Rank across multiple queries.

    Each query dict has keys: results (list[str]), ground_truth (str | list[str]).
    """
    if not queries:
        return 0.0
    total = sum(
        compute_mrr(q["results"], q["ground_truth"], k=k)
        for q in queries
    )
    return total / len(queries)


# ===========================================================================
# TestMRR
# ===========================================================================


class TestMRR:
    """MRR-1 ~ MRR-6: MRR calculation correctness."""

    def test_mrr_perfect_rank(self):
        """MRR-1: ground truth at rank 1 -> MRR = 1.0."""
        assert compute_mrr(["id_a", "id_b", "id_c"], "id_a") == 1.0

    def test_mrr_second_rank(self):
        """MRR-2: ground truth at rank 2 -> MRR = 0.5."""
        assert compute_mrr(["id_a", "id_b", "id_c"], "id_b") == 0.5

    def test_mrr_third_rank(self):
        """MRR-3: ground truth at rank 3 -> MRR = 1/3."""
        mrr = compute_mrr(["id_a", "id_b", "id_c"], "id_c")
        assert abs(mrr - 1.0 / 3) < 1e-6

    def test_mrr_not_in_topk(self):
        """MRR-4: ground truth not in results -> MRR = 0."""
        assert compute_mrr(["id_a", "id_b", "id_c"], "id_x") == 0.0

    def test_mrr_empty_results(self):
        """MRR-6: empty results -> MRR = 0, no exception."""
        assert compute_mrr([], "id_a") == 0.0

    def test_mrr_with_k_cutoff(self):
        """MRR with k=2: ground truth at rank 3 is beyond cutoff -> MRR = 0."""
        assert compute_mrr(["id_a", "id_b", "id_c"], "id_c", k=2) == 0.0

    def test_mrr_multiple_ground_truths(self):
        """MRR with list of expected IDs: first match counts."""
        mrr = compute_mrr(["id_a", "id_b", "id_c"], ["id_b", "id_c"])
        assert mrr == 0.5  # id_b found at rank 2


class TestMeanMRR:
    """MRR-5: Mean MRR across multiple queries."""

    def test_mean_mrr_two_queries(self):
        """MRR-5: average of perfect and second rank."""
        queries = [
            {"results": ["a", "b"], "ground_truth": "a"},  # MRR = 1.0
            {"results": ["a", "b"], "ground_truth": "b"},  # MRR = 0.5
        ]
        mean = compute_mean_mrr(queries)
        assert abs(mean - 0.75) < 1e-6

    def test_mean_mrr_all_miss(self):
        """All queries miss -> mean MRR = 0."""
        queries = [
            {"results": ["a", "b"], "ground_truth": "x"},
            {"results": ["a", "b"], "ground_truth": "y"},
        ]
        assert compute_mean_mrr(queries) == 0.0

    def test_mean_mrr_empty_queries(self):
        """No queries -> mean MRR = 0."""
        assert compute_mean_mrr([]) == 0.0

    def test_mean_mrr_with_k(self):
        """Mean MRR with k cutoff."""
        queries = [
            {"results": ["a", "b", "c"], "ground_truth": "a"},  # MRR@2 = 1.0
            {"results": ["a", "b", "c"], "ground_truth": "c"},  # MRR@2 = 0 (c at rank 3)
        ]
        mean = compute_mean_mrr(queries, k=2)
        assert abs(mean - 0.5) < 1e-6


# ===========================================================================
# TestParameterSets
# ===========================================================================


class TestParameterSets:
    """PARAM-1 ~ PARAM-2: Parameter set definitions and isolation."""

    PARAM_SETS = {
        "baseline":   {"MARGIN_THRESHOLD": 0.05, "MAX_CONTEXT_BOOST": 0.10, "GENERAL_CONTEXT_BOOST": 0.07},
        "medium":     {"MARGIN_THRESHOLD": 0.03, "MAX_CONTEXT_BOOST": 0.15, "GENERAL_CONTEXT_BOOST": 0.10},
        "aggressive": {"MARGIN_THRESHOLD": 0.02, "MAX_CONTEXT_BOOST": 0.20, "GENERAL_CONTEXT_BOOST": 0.14},
    }

    def test_three_parameter_sets_defined(self):
        """PARAM-1: All three parameter sets are defined."""
        assert set(self.PARAM_SETS.keys()) == {"baseline", "medium", "aggressive"}

    def test_parameter_values_in_range(self):
        """PARAM-1: All parameter values are in valid range."""
        for name, params in self.PARAM_SETS.items():
            assert 0 < params["MARGIN_THRESHOLD"] < 1, f"{name} MARGIN_THRESHOLD out of range"
            assert 0 < params["MAX_CONTEXT_BOOST"] < 1, f"{name} MAX_CONTEXT_BOOST out of range"
            assert 0 < params["GENERAL_CONTEXT_BOOST"] < 1, f"{name} GENERAL_CONTEXT_BOOST out of range"
            assert params["GENERAL_CONTEXT_BOOST"] < params["MAX_CONTEXT_BOOST"], (
                f"{name}: GENERAL should be less than MAX"
            )

    def test_aggressive_has_lowest_threshold(self):
        """Aggressive should have the lowest margin threshold."""
        assert self.PARAM_SETS["aggressive"]["MARGIN_THRESHOLD"] < self.PARAM_SETS["medium"]["MARGIN_THRESHOLD"]
        assert self.PARAM_SETS["medium"]["MARGIN_THRESHOLD"] < self.PARAM_SETS["baseline"]["MARGIN_THRESHOLD"]

    def test_aggressive_has_highest_boost(self):
        """Aggressive should have the highest boost value."""
        assert self.PARAM_SETS["aggressive"]["MAX_CONTEXT_BOOST"] > self.PARAM_SETS["medium"]["MAX_CONTEXT_BOOST"]
        assert self.PARAM_SETS["medium"]["MAX_CONTEXT_BOOST"] > self.PARAM_SETS["baseline"]["MAX_CONTEXT_BOOST"]
