# Evaluation sets

Small, author-written sets (invented messages, emails and URLs in English,
Hindi, Hinglish and Tamil). They measure regressions in TruthShield's rules
and retrieval. **They are not real-world accuracy figures.**

## Fraud detection: how each set has been used

| File | Items | Role | Used to change rules? |
|---|---|---|---|
| `fraud_eval.jsonl` | 81 | development | yes, from the start |
| `fraud_holdout.jsonl` | 56 | validation | measured first, then used to fix error classes |
| `fraud_blind.jsonl` | 52 | validation | measured first (recall 0.77), then used to fix error classes |
| `fraud_blind2.jsonl` | 54 | validation | measured first (P 0.95, R 0.71, FPR 0.04), then used to fix error classes |
| `fraud_final_blind.jsonl` | 65 | **final blind test** | **no; never tune on it** |

Final blind test, measured once on 20 October 2026 (a result at MEDIUM or
above counts as flagged):

| Rules | Precision | Recall | F1 | FPR | FNR |
|---|---|---|---|---|---|
| Phase 1 (commit f8220e9) | 0.850 | 0.486 | 0.618 | 0.100 | 0.514 |
| Current | 0.971 | 0.943 | 0.957 | 0.033 | 0.057 |

Known errors on it, deliberately left unfixed so the set stays blind: a
spaced-out "O T P" request (missed), a job "training fee" (missed), and a
genuine university "registration fee" reminder (false alarm). Fixing them
needs new development examples of the same classes, written separately.

    python -m truthshield.investigations.evaluation tests/eval/fraud_final_blind.jsonl --by

## Retrieval

`retrieval_corpus.jsonl` (25 passages) and `retrieval_queries.jsonl` (20
claims, half paraphrased): `python -m truthshield.rag.evaluation`.
