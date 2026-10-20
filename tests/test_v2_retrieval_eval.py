"""
Retrieval evaluation (truthshield/rag/evaluation.py).

The metric functions are checked by hand-computed cases; the evaluation set
guards retrieval quality against regressions. Measured with the lexical
hashing embedder on 20 October 2026 (store / full RAG): Recall@5 0.975 /
0.975, MRR 0.950 / 1.000, NDCG@5 0.939 / 0.977. Small, author-written set:
regression numbers, not real-world accuracy.
"""

import math

import pytest

from truthshield.rag.evaluation import evaluate, metrics


class TestMetrics:
    def test_a_perfect_ranking(self):
        m = metrics(["a", "b", "x"], ["a", "b"], k=3)
        assert m == {"recall": 1.0, "precision": pytest.approx(2 / 3), "mrr": 1.0, "ndcg": pytest.approx(1.0)}

    def test_a_relevant_document_found_late(self):
        m = metrics(["x", "y", "a"], ["a"], k=3)
        assert m["recall"] == 1.0 and m["mrr"] == pytest.approx(1 / 3)
        assert m["ndcg"] == pytest.approx((1 / math.log2(4)) / 1.0)

    def test_nothing_relevant_retrieved(self):
        assert metrics(["x", "y"], ["a"], k=2) == {"recall": 0.0, "precision": 0.0, "mrr": 0.0, "ndcg": 0.0}

    def test_relevant_beyond_k_does_not_count_for_recall(self):
        m = metrics(["x", "y", "a"], ["a"], k=2)
        assert m["recall"] == 0.0 and m["mrr"] == pytest.approx(1 / 3)


def test_retrieval_quality_holds_on_the_evaluation_set():
    report = evaluate(k=5)
    for stage in ("store", "rag"):
        m = report["stages"][stage]
        assert m["recall"] >= 0.95, (stage, report["misses"][stage])
        assert m["mrr"] >= 0.9, stage
    # Reranking must not make the ordering worse than raw hybrid search.
    assert report["stages"]["rag"]["ndcg"] >= report["stages"]["store"]["ndcg"]
