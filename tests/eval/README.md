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
| `fraud_dev2.jsonl` | 20 | development | yes (spelled-out OTP/PIN/KYC, fees to get hired, earnings + registration fee, routine fees) |
| `fraud_final_blind.jsonl` | 65 | former final blind | items never used to write rules, but its errors chose which classes `fraud_dev2` covers, so it now flatters those classes |
| `fraud_final_blind2.jsonl` | 55 | **final blind test** | **no; never tune on it** |

Final blind test, measured once on 20 October 2026 (a result at MEDIUM or
above counts as flagged):

| Rules | Precision | Recall | F1 | FPR | FNR |
|---|---|---|---|---|---|
| Phase 1 (commit f8220e9) | 0.850 | 0.486 | 0.618 | 0.100 | 0.514 |
| Current | 0.971 | 0.943 | 0.957 | 0.033 | 0.057 |

Its three errors (a spelled-out "O T P", a job "training fee", a genuine
exam "registration fee" flagged) were then fixed from new development
examples (`fraud_dev2`); re-measured it reads P 1.000 R 1.000, which is why
it is no longer the blind set.

**Current final blind test**, `fraud_final_blind2.jsonl`, measured once on
20 October 2026 with the rules as of commit "audit batch 4":

| Rules | Precision | Recall | F1 | FPR | FNR |
|---|---|---|---|---|---|
| Current | 0.929 | 0.867 | 0.897 | 0.080 | 0.133 |

This is the honest estimate. Known errors, left unfixed so the set stays
blind (next step: development examples of each class, then a new blind set):

- missed: "forward that 4 digit number" (no "code"/"OTP" word)
- missed: "confirm the O-T-P" ("confirm" is not a request verb in the rules)
- missed: a job fee stated as "Pay Rs 1,800 ... before your joining date" (no "fee" word)
- missed: Hinglish lottery "jeete hain ... processing fee jama karein"
- false alarm: "Congratulations, you have been selected" in a genuine job offer
- false alarm: a news report describing a scam gang's messages

    python -m truthshield.investigations.evaluation tests/eval/fraud_final_blind2.jsonl --by

## Retrieval

`retrieval_corpus.jsonl` (25 passages) and `retrieval_queries.jsonl` (20
claims, half paraphrased): `python -m truthshield.rag.evaluation`.
