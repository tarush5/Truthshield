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

### Confidence calibration (`--calibration`)

Measured on `fraud_final_blind2.jsonl` (21 October 2026), not fitted:

| Confidence band | Items | Verdict accuracy | Mean stated confidence |
|---|---|---|---|
| LOW | 25 | 0.84 | 0.35 |
| MODERATE | 17 | 0.88 | 0.72 |
| HIGH | 13 | 1.00 | 0.80 |

Accuracy rises with the band, which is the property the confidence exists
for, and all four missed scams sit in the LOW band. Stated confidence is
below measured accuracy (weighted gap 0.32), largely by design: results with
no signal are capped at 0.35 because absence of signals is weak evidence.
The formula was not recalibrated: fitting it to author-written sets would
measure the author, not the world. Reviewer decisions
(`GET /api/v1/admin/reviews/accuracy`, by confidence band) are where real
calibration data accumulates.

### Cycles 3 and 4 (21 October 2026)

Protocol for each cycle: write the final test set first, commit it alone
(sealed), develop fixes only on a separate dev set plus the *previous*
final set's known errors, then run the sealed set exactly once against the
old and the new rules. Every set is author-written; the sets carry the
author's bias and none is evidence of real-world accuracy.

| Set | Rules | Precision | Recall | F1 | FPR | Notes |
|---|---|---|---|---|---|---|
| `fraud_final_blind3` (64) | before cycle 3 | 0.861 | 0.969 | 0.912 | 0.156 | |
| `fraud_final_blind3` (64) | after cycle 3 | 0.861 | 0.969 | 0.912 | 0.156 | dev3 fixes did not generalise |
| `fraud_final_blind4` (64) | after cycle 3 | 0.806 | 0.781 | 0.794 | 0.188 | |
| `fraud_final_blind4` (64) | after cycle 4 | 0.867 | 0.812 | 0.839 | 0.125 | 95% CIs overlap: not conclusive |

`fraud_final_blind4` mirrors blind3's category mix one-for-one, but it was
written after blind3's errors were known, so it is not free of the author's
knowledge of those classes. Cycle 4's fixes were limited to blind3's error
classes and `fraud_dev4`.

`fraud_final_blind3` is now development data (its errors were fixed in
cycle 4). `fraud_final_blind4` was the reference until cycle 5; its errors,
listed here, were fixed in cycle 5 and it is now development data too:

- missed: Tamil OTP request ("பகிரவும்" -- share)
- missed: "share the c0de" (a code, not an "OTP", with look-alike characters)
- missed: hiring "transfer Rs ... before onboarding" with no fee or pay word
- missed: QR scan + "enter your UPI PIN, the money will come" phrasing
- missed: romance-to-crypto-trading pitch
- missed: paid Google Maps review task (scored 25, below MEDIUM)
- false alarm: RBI awareness message ("never ask for your PIN ... OTP")
- false alarm: an Income Tax refund-credited notice
- false alarm: police awareness message about parcel/drugs calls
- false alarm: a bank's Re-KYC reminder that says no link is sent

Known gap found in development (fixed in cycle 5): "pay the penalty today to
avoid arrest" with no other cue was not caught.

### Cycle 5 (21 October 2026)

| Set | Rules | Precision | Recall | F1 | FPR |
|---|---|---|---|---|---|
| `fraud_final_blind5` (64) | after cycle 4 | 0.889 | 0.750 | 0.814 | 0.094 |
| `fraud_final_blind5` (64) | after cycle 5 | 0.897 | 0.812 | 0.852 | 0.094 |

Two more scams caught, no new false alarm; 95% CIs overlap (recall
[0.65, 0.91]), so not conclusive. blind5 has blind3's category mix and was
written after blind4's errors were known. **`fraud_final_blind5` is the
current honest estimate.** Its errors, left unfixed:

- missed: "read out the six digit message" (a "message", not a "code")
- missed: Hindi lottery asking to send ("भेजें") a processing fee
- missed: "You have won a Samsung Galaxy for Rs 199" brand prize (34, below MEDIUM)
- missed: Hindi request for card number, CVV and OTP (no Hindi OTP-request rule)
- missed: fake e-challan with a payment link (no challan rule)
- missed: dating-app forex pitch with "the returns are guaranteed" (word order)
- false alarm: a genuine bank OTP with "If you did not request this, call ..."
- false alarm: a CERT-In advisory about fake TRAI disconnection calls
- false alarm: a lottery results announcement

Five cycles in, each new author-written set surfaces new phrasings the
rules miss. That pattern, not any single number, is the main finding: rule
coverage keeps growing, but real-world accuracy can only be measured on
independent, labelled real messages.

## Retrieval

`retrieval_corpus.jsonl` (25 passages) and `retrieval_queries.jsonl` (20
claims, half paraphrased): `python -m truthshield.rag.evaluation`.
