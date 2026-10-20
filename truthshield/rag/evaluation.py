"""
Retrieval evaluation: Recall@K, Precision@K, MRR and NDCG@K.

    python -m truthshield.rag.evaluation [--k 5] [--embedder hashing|sentence-transformers]

Loads a labelled corpus into an in-memory evidence store (never the
application database), runs every query through the real retrieval path with
live search switched off, and scores the ranked documents against the
labelled relevant ones. Two stages are scored separately so a regression can
be located:

- `store`  -- hybrid search alone (semantic + keyword, fused with RRF)
- `rag`    -- the full engine: query expansion, relevance floor, reranking

The default set (tests/eval/retrieval_*.jsonl) is small and written for this
project: 25 passages, including on-topic distractors, and 20 claims, half of
them paraphrased so keywords alone do not find the answer. The numbers
measure regressions in retrieval; they are not real-world accuracy.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Sequence

EVAL_DIR = Path(__file__).resolve().parents[2] / "tests" / "eval"


def _load(path: Path) -> List[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def metrics(ranked: Sequence[str], relevant: Sequence[str], k: int) -> Dict[str, float]:
    """Binary-relevance metrics for one query's ranked document ids."""
    top = list(ranked[:k])
    rel = set(relevant)
    hits = [1 if d in rel else 0 for d in top]
    first = next((i for i, d in enumerate(ranked) if d in rel), None)
    dcg = sum(h / math.log2(i + 2) for i, h in enumerate(hits))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(rel), k)))
    return {
        "recall": sum(hits) / len(rel) if rel else 0.0,
        "precision": sum(hits) / k,
        "mrr": 1.0 / (first + 1) if first is not None else 0.0,
        "ndcg": dcg / ideal if ideal else 0.0,
    }


def _session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from truthshield.infra.database import Base
    import truthshield.infra.models  # noqa: F401  (registers the tables)

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _embedder(name: Optional[str]):
    from truthshield.providers.embeddings import HashingEmbedding

    if name in (None, "hashing"):
        return HashingEmbedding()
    from truthshield.providers.embeddings import SentenceTransformerEmbedding

    model = SentenceTransformerEmbedding()
    if not model.available:
        raise SystemExit(f"The semantic embedder is unavailable ({model.unavailable_reason}). "
                         "Set ENABLE_ML_DETECTORS=true with sentence-transformers installed.")
    return model


def evaluate(*, k: int = 5, embedder: Optional[str] = None,
             corpus: Optional[Path] = None, queries: Optional[Path] = None) -> dict:
    from truthshield.providers.search import NullSearchProvider
    from truthshield.rag import EvidenceStore, RAGEngine

    docs = _load(corpus or EVAL_DIR / "retrieval_corpus.jsonl")
    items = _load(queries or EVAL_DIR / "retrieval_queries.jsonl")
    session = _session()
    model = _embedder(embedder)
    store = EvidenceStore(session, model)

    url_to_doc: Dict[str, str] = {}
    for d in docs:
        url = f"https://{d['publisher']}/eval/{d['id']}"
        store.ingest(url=url, title=d["title"], content=d["text"], provider="eval", publisher=d["publisher"])
        url_to_doc[url] = d["id"]

    def unique(urls: Sequence[str]) -> List[str]:
        out: List[str] = []
        for u in urls:
            doc = url_to_doc.get(u)
            if doc and doc not in out:
                out.append(doc)
        return out

    engine = RAGEngine(session, embedder=model, search=NullSearchProvider("evaluation"), min_local_hits=0, top_k=k * 2)
    per_stage: Dict[str, List[dict]] = {"store": [], "rag": []}
    for item in items:
        store_ranked = unique([c.url for c in store.search(item["claim"], limit=k * 4)])
        rag_ranked = unique([p["url"] for p in asyncio.run(engine.retrieve(item["claim"])).passages])
        per_stage["store"].append({"id": item["id"], "ranked": store_ranked, **metrics(store_ranked, item["relevant"], k)})
        per_stage["rag"].append({"id": item["id"], "ranked": rag_ranked, **metrics(rag_ranked, item["relevant"], k)})
    session.close()

    def mean(rows: List[dict], key: str) -> float:
        return round(sum(r[key] for r in rows) / len(rows), 3) if rows else 0.0

    return {
        "k": k,
        "embedder": model.name,
        "queries": len(items),
        "documents": len(docs),
        "stages": {
            stage: {key: mean(rows, key) for key in ("recall", "precision", "mrr", "ndcg")}
            for stage, rows in per_stage.items()
        },
        "misses": {
            stage: [r["id"] for r in rows if r["recall"] < 1.0]
            for stage, rows in per_stage.items()
        },
        "per_query": per_stage,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--embedder", choices=["hashing", "sentence-transformers"], default="hashing")
    args = parser.parse_args(argv)

    report = evaluate(k=args.k, embedder=args.embedder)
    print(f"{report['queries']} queries over {report['documents']} documents, embedder {report['embedder']}, K={report['k']}")
    for stage, m in report["stages"].items():
        print(f"  {stage:<6} Recall@K {m['recall']:.3f}  Precision@K {m['precision']:.3f}  "
              f"MRR {m['mrr']:.3f}  NDCG@K {m['ndcg']:.3f}   incomplete recall: {', '.join(report['misses'][stage]) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
