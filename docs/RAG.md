# Evidence retrieval (RAG)

Code: `truthshield/rag/` (store, retrieval engine, reranking, text utilities),
`truthshield/providers/` (embeddings, search, LLM), and
`truthshield/investigations/engines/evidence.py` (adjudication) and
`investigations/interpret.py` (grounded interpretation).

## Pipeline

```
claim
  → query expansion        original · keywords · negation-neutral · entities
  → hybrid store search    semantic (pgvector cosine / numpy)  ┐ Reciprocal
                           keyword  (Postgres FTS / BM25)      ┘ Rank Fusion
  → enough relevant local evidence?  no → live search → ingest results → search again
  → metadata filters       category · credibility floor · domain allow/deny · publication window
  → rerank                 feature reranker (or a cross-encoder via RERANKER_MODEL)
  → passage extraction     best 2-sentence window per chunk
  → adjudication           1.x deterministic stance + verdict (no LLM)
  → credibility guard      no SUPPORTED/CONTRADICTED on low-credibility sources alone
  → (optional) LLM interpretation over the findings, citations validated
```

## The store

| Table | Holds |
|---|---|
| `sources` | One row per publisher domain: category, credibility, `curated` flag |
| `evidence_documents` | URL (unique by SHA-256), title, published/retrieved times, `content_scope` (`snippet`, `full_text`, `uploaded`), provider |
| `evidence_chunks` | Sentence-aware chunks (~700 chars, 1-sentence overlap), `embedding vector(384)`, `embedding_model` |

On PostgreSQL the `vector` extension provides the column, an **HNSW index
(cosine)** serves nearest-neighbour search, and a **GIN index on
`to_tsvector('simple', text)`** serves keyword search. On SQLite (development
and tests) the same vectors are stored as JSON and scored in Python.

Vectors from different models are never compared: every query filters on
`embedding_model`.

The store is a cache of the web plus curated uploads. Refetching a URL with
changed content replaces its chunks. Investigations snapshot the passages they
used into their own result, so history never changes underneath them.

## Embeddings

| Provider | Kind | When |
|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | semantic | ML extras installed and `ENABLE_ML_DETECTORS=true` |
| `hashing-ngram-v1` | **lexical** | Otherwise. Signed feature hashing of word unigrams and bigrams |

The lexical embedder measures shared vocabulary, not meaning. It keeps the
store functional on a bare install and is labelled `lexical` everywhere a
score is shown. Relevance floors differ by kind: 0.40 for semantic (the 1.x
measured floor) and 0.15 for lexical.

## Reranking

`feature-weighted-v1` is not learned. Its score is:

```
0.55 · relevance (cosine) + 0.20 · keyword (normalised) + 0.15 · source credibility + 0.10 · recency
```

Recency halves every 365 days. Every component is returned with each
passage, so the ordering can be challenged. Setting `RERANKER_MODEL` to a
cross-encoder (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2`) switches to a
learned reranker when it loads, and falls back to the feature reranker when
it does not.

## Adjudication and its guards

Stance and verdict come from the 1.x engine with its LLM verdict paths
**switched off**. The deterministic path (NLI when installed, lexical stance
rules otherwise) is the one the frozen-evidence benchmark measures. On top
of it:

- **Credibility guard:** a SUPPORTED or CONTRADICTED decision where every
  decisive source is below 0.7 credibility (and none is OFFICIAL or
  PRIMARY) is downgraded to INSUFFICIENT_EVIDENCE, with the reason stated.
- **Claim-quality gate (text engine):** instructions, links, statements
  addressed to the recipient ("you have won"), fragments under 5 words and
  passages over 60 words are not sent for checking. Transactional documents
  (invoices, receipts, statements) skip claim checking entirely.

## Grounded interpretation

When an LLM provider is configured, the model receives the **findings**
(numbered signals S1…, numbered sources [1]…, the computed score). It never
receives the raw submission. Excerpts are sanitised and fenced in a
`<findings>` data block. The output must cite existing ids, and must not
state a different score. Otherwise it is discarded and the reason recorded.
It is shown as "LLM interpretation, not evidence" with model and token usage.

## Offline

With `OFFLINE_MODE=true` live search is unavailable, but the **local store
is still consulted**: an offline deployment answers from curated documents
and says that live search did not run.

## Measured behaviour (dev machine, SQLite, lexical embeddings)

These are single observations, not a benchmark:

- Phishing SMS: claim gate removes the instruction → no retrieval, 0.42 s.
- Health-misinformation demo with live search: about 4–5 s end to end.
  Subjectless fragments are no longer sent ("It is 100% proven" had been
  marked SUPPORTED by unrelated finance pages before the gate and guard).
- Invoice PDF: no claim retrieval (transactional), 1.4 s.

Retrieval quality on the frozen fixture has **not** been re-measured for the
store-first path. That is the next evaluation task (Phase 6, `evaluate.py`:
Recall@K, MRR, NDCG, citation correctness).
