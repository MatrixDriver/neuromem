"""Evaluate context parameter combinations using MRR metric.

Usage:
    uv run python scripts/eval_context_params.py --database-url DATABASE_URL --user-id USER_ID --dataset DATASET_JSON --embedding-api-key API_KEY
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from neuromem import NeuroMemory
from neuromem.providers.siliconflow import SiliconFlowEmbedding
from neuromem.services.context import ContextService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

PARAM_SETS = {
    "baseline":   {"MARGIN_THRESHOLD": 0.05, "MAX_CONTEXT_BOOST": 0.10, "GENERAL_CONTEXT_BOOST": 0.07},
    "medium":     {"MARGIN_THRESHOLD": 0.03, "MAX_CONTEXT_BOOST": 0.15, "GENERAL_CONTEXT_BOOST": 0.10},
    "aggressive": {"MARGIN_THRESHOLD": 0.02, "MAX_CONTEXT_BOOST": 0.20, "GENERAL_CONTEXT_BOOST": 0.14},
}


def mrr_at_k(results: list[str], expected: list[str], k: int) -> float:
    """Compute Mean Reciprocal Rank at k."""
    for i, rid in enumerate(results[:k]):
        if rid in expected:
            return 1.0 / (i + 1)
    return 0.0


async def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate context parameter combinations using MRR")
    parser.add_argument("--database-url", required=True, help="PostgreSQL async connection URL")
    parser.add_argument("--user-id", required=True, help="User ID to evaluate")
    parser.add_argument("--dataset", required=True, help="Path to evaluation dataset JSON")
    parser.add_argument("--embedding-api-key", required=True, help="SiliconFlow API key")
    args = parser.parse_args()

    with open(args.dataset) as f:
        dataset = json.load(f)

    logger.info("Loaded %d evaluation queries", len(dataset))

    embedding = SiliconFlowEmbedding(api_key=args.embedding_api_key)

    results_table: dict[str, dict[str, float]] = {}

    for param_name, params in PARAM_SETS.items():
        logger.info("Evaluating parameter set: %s", param_name)

        ContextService.MARGIN_THRESHOLD = params["MARGIN_THRESHOLD"]
        ContextService.MAX_CONTEXT_BOOST = params["MAX_CONTEXT_BOOST"]
        ContextService.GENERAL_CONTEXT_BOOST = params["GENERAL_CONTEXT_BOOST"]

        nm = NeuroMemory(
            database_url=args.database_url,
            embedding=embedding,
        )
        await nm.init()

        mrr3_scores: list[float] = []
        mrr5_scores: list[float] = []

        for entry in dataset:
            query = entry["query"]
            expected = entry["expected_top3"]

            recall_results = await nm.recall(
                user_id=args.user_id,
                query=query,
                limit=5,
            )

            result_ids = [r["id"] for r in recall_results.get("merged", [])]
            mrr3_scores.append(mrr_at_k(result_ids, expected, 3))
            mrr5_scores.append(mrr_at_k(result_ids, expected, 5))

        await nm.close()

        avg_mrr3 = sum(mrr3_scores) / len(mrr3_scores) if mrr3_scores else 0.0
        avg_mrr5 = sum(mrr5_scores) / len(mrr5_scores) if mrr5_scores else 0.0

        results_table[param_name] = {"MRR@3": avg_mrr3, "MRR@5": avg_mrr5}
        logger.info("  %s: MRR@3=%.4f, MRR@5=%.4f", param_name, avg_mrr3, avg_mrr5)

    print("\n" + "=" * 60)
    print(f"{'Parameter Set':<15} {'MRR@3':>10} {'MRR@5':>10}")
    print("-" * 60)
    for name, scores in results_table.items():
        print(f"{name:<15} {scores['MRR@3']:>10.4f} {scores['MRR@5']:>10.4f}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
