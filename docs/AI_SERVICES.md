# AI services

TruthShield does not send inputs to a language model and relay its answer.
Each engine is a separate, testable pipeline that states **how** it knows
what it reports: heuristic rule, trained model, retrieved source, or LLM
interpretation. It also states what it could not check.

Code: `truthshield/investigations/`.

## 1. Engine contract

```
Engine.run(ctx: InvestigationContext) -> EngineResult
  status        ok | unavailable | error | not_applicable
  signals       [Signal]           → risk engine
  features      {name: number}     → stored, shown, used by future ML models
  artifacts     {entities, claims, page, …}
  predictions   [ModelPrediction]  → model_predictions table (name, version, input hash)
  limitations   [str]              → "uncertainties" in the result
  duration_ms
```

Engines never raise. A failure becomes `status="error"` with a limitation,
so "could not check" is never mistaken for "checked and clean".

## 2. Phase 1 engines

### 2.1 Text engine (`text`, heuristic, v1.0.0)

```
raw text → language detection → normalisation → sentence segmentation →
entity extraction → claim extraction → intent detection →
scam / phishing / manipulation signals → prompt-injection check
```

| Step | Method | Notes |
|---|---|---|
| Language | Unicode script ranges for Devanagari (hi) and Tamil (ta), then `langdetect` | The original text is always preserved. Unsupported languages are analysed with a limitation noted |
| Normalisation | NFKC, zero-width removal, whitespace collapse | **Hidden zero-width characters** are a signal (filter evasion) |
| Sentences | Regex on `. ! ? ।` | |
| Entities | URLs, emails, phones, UPI handles, crypto addresses (1.x `classify`); **amounts** (₹/Rs/INR/$/lakh/crore); **dates**; **organisations and brands** (watched-brand lexicon) | Person and location NER need a spaCy model. Without one this is reported as a limitation, not skipped silently |
| Claims | 1.x `ClaimExtractor` (spaCy if present, rule-based fallback) | IDs `C1…` |
| Intent | Rule-based: `credential_request`, `payment_request`, `otp_request`, `prize_claim`, `account_threat`, `link_click` | |
| Scam and phishing | 1.x `message_scam` + `email_fraud` detectors, extended in 2.0 | Hinglish-, Hindi- and Tamil-aware, category-specific; negation- and context-aware (see 2.1.1) |
| Manipulation | 1.x deception register (`urgency`, `authority`, `suppression`, `engagement_bait`, `financial`, …) | |
| Prompt injection | Patterns aimed at AI systems ("ignore previous instructions", "reveal your system prompt") | Flagged as `info`. Such text is data here, never instructions |

#### 2.1.1 Scam patterns and context (October 2026)

Patterns cover bank/KYC, OTP and PIN requests (including "forward the code I sent by mistake",
QR "verification", card-detail harvesting), delivery and customs, prizes, paid-task jobs,
loans, investments (guaranteed or multiplied returns), crypto, tech support and fake renewals,
government and police threats ("digital arrest", FIRs, SIM deactivation, seized parcels),
**advance fees** (processing, clearance, release charges; inheritances), **utility
disconnection** (`UTILITY_SCAM`), **impersonation of someone you know** (new number, gift
cards, the boss in a meeting), requests for secrecy, romance-with-a-fee and billing pretexts.

A match is ignored when context shows it is not the scam:

| Context | Example that is *not* flagged |
|---|---|
| Negated | "Do not share this OTP with anyone", "no processing fee" |
| Awareness | "Beware of digital arrest scams", "report fraud on 1930" |
| Routine | "Share OTP 4417 with the delivery agent at the time of delivery" |
| Completed | "Your KYC has been successfully updated" (only a *demand* to update counts) |

`no` / `zero` / `without` only negate a fee: "a client with no next of kin" is still flagged.

#### 2.1.2 Evaluation

```bash
python -m truthshield.investigations.evaluation tests/eval/fraud_blind.jsonl
```

Three labelled sets in `tests/eval/`, written for this project (invented messages, emails
and URLs in English, Hindi, Hinglish and Tamil). A result at MEDIUM or above counts as a flag.
These numbers measure the rules against these sets. **They are not real-world accuracy
figures and must not be presented as such.**

| Set | Items | Role | 1.x rules (P / R / FPR) | 2.0 rules (P / R / FPR) |
|---|---|---|---|---|
| `fraud_eval` | 81 | developing the rules | 0.96 / 0.55 / 0.03 | 1.00 / 1.00 / 0.00 (tuned on it) |
| `fraud_holdout` | 56 | first unseen set | 0.67 / 0.37 / 0.17 | 0.84 / 0.78 / 0.14 on first sight; then used to fix error classes |
| `fraud_blind` | 52 | second unseen set | 1.00 / 0.35 / 0.00 | **1.00 / 0.77 / 0.00** on first sight |
| `fraud_blind2` | 54 | third unseen set (20 Oct 2026) | not measured | **0.95 / 0.71 / 0.04** on first sight, with the rules as they stood after `fraud_blind` |

Later sets (October 2026) follow a stricter protocol -- each final set is committed alone
before any rule change and measured exactly once against the old and the new rules; fixes are
developed on separate `fraud_dev*` sets. Full history and every remaining error are in
`tests/eval/README.md`:

| Final set (64 items) | Before cycle | After cycle (P / R / FPR) |
|---|---|---|
| `fraud_final_blind3` | 0.86 / 0.97 / 0.16 | 0.86 / 0.97 / 0.16 (cycle 3 did not generalise) |
| `fraud_final_blind4` | 0.81 / 0.78 / 0.19 | 0.87 / 0.81 / 0.13 |
| `fraud_final_blind5` | 0.89 / 0.75 / 0.09 | **0.90 / 0.81 / 0.09** (current reference) |

Each rate carries a 95% Wilson interval of about ±0.13 at this size, so no single cycle's
change is statistically conclusive. `fraud_final_blind5` has no near-duplicate (3-gram Jaccard
≥ 0.4) in any other set; a test enforces this. Three of blind3's items were found to be
rewordings of development items. Confidence calibration (`--calibration`): accuracy rises
with the confidence band; stated confidence is conservative by design and was not refitted.

The rows below this point describe the earlier sets.

The two blind rows are the honest estimates of how the rules generalise. `fraud_blind2`
exposed sextortion (now `EXTORTION`), Hindi and Tamil police and prize-fee wording, "deposit
the GST first" lottery fees, fake auto-renewal refund calls, doubled-letter lookalikes
(`flipkarrt`), shortened links named after a bank, and one awareness false alarm. The blind
sets' misses were then fixed, so all three sets now pass and serve as a regression guard (`tests/test_v2_accuracy.py`
requires recall ≥ 0.95 and a false-positive rate ≤ 0.04 on each). New patterns should be
checked against a fresh set written before tuning.

### 2.2 URL engine (`url`, heuristic, v1.0.0)

For every URL (up to 5), it computes the spec's feature vector:

| Feature | Definition |
|---|---|
| `url_length`, `domain_length` | characters |
| `subdomain_count` | labels left of the registrable domain |
| `path_depth` | non-empty path segments |
| `special_character_count` | `@ - _ ~ % = & ?` and similar |
| `digit_ratio` | digits ÷ characters in the host |
| `entropy` | Shannon entropy of the host (bits/char) |
| `https` | 0/1 |
| `suspicious_keyword_score` | harvest vocabulary hits (login, verify, kyc, …), 0–1 |
| `brand_similarity` | max normalised edit-similarity between the registrable label and a watched brand |
| `encoded_character_count`, `query_param_count`, `tld` | |

Signals: all 1.x structure rules (punycode, mixed script, IP host, brand in
subdomain, cheap TLD, shortener, `@` userinfo, credential path, insecure
credential page, free hosting), plus **typosquatting** (brand similarity ≥
0.8 without an exact match, or a token that *becomes* the brand once swapped characters
are read back: `faceb00k`, `netf1ix`, `instagrarn`) and **high-entropy host**. The watched
brands include the Indian government, banking, retail and telecom names most imitated
(Income Tax, IRCTC, UIDAI, EPFO, India Post, Flipkart, Jio, Airtel, …); those match only
as whole tokens or by character swaps, never by edit distance, because several are one
letter from ordinary words (`myntra` / `mantra`). "gov" inside a domain anyone can register
is treated as a government lookalike.

**Page retrieval** runs only when `URL_FETCH_ENABLED=true` and the process is
not offline. It goes through the SSRF guard with a 3 s connect / 6 s read
timeout, a 2 MB cap and a recorded redirect chain. Scripts are never
executed. It extracts the title, description, forms, password fields,
cross-domain form actions, external scripts and links. From those come the
signals **credential form posts elsewhere**, **password field over HTTP**,
**brand named in the page but not in the domain**, and **redirect chain
crosses domains**.

Results are cached per URL in Redis (`URL_CACHE_TTL_SECONDS`).

**Not checked (reported as uncertainty):** WHOIS age, certificate details,
reputation feeds. The `reputation` family is `assessed: false` until a
threat-intel provider is configured (Phase 7). The UI shows it as
*not assessed*, not as zero.

### 2.3 Evidence engine (`evidence`, retrieval, v2.0.0)

For each extracted claim (at most `MAX_CLAIMS_PER_SUBMISSION`), it runs RAG
retrieval (see [RAG.md](RAG.md)) and deterministic adjudication. All claims are
retrieved in one batch: the live searches the store cannot answer run
**concurrently**, so three claims cost about one search, not three. The verdict maps to the spec vocabulary:

| 1.x verdict | 2.0 assessment |
|---|---|
| VERIFIED, LIKELY TRUE, PARTIALLY TRUE | `SUPPORTED` |
| FALSE, LIKELY FALSE, MISLEADING | `CONTRADICTED` |
| MIXED EVIDENCE | `MIXED` |
| INSUFFICIENT EVIDENCE | `INSUFFICIENT_EVIDENCE` (never forced) |

`CONTRADICTED` claims produce `evidence`-family signals with
`provenance="retrieved"`. Every source carries its title, URL, publisher
domain, credibility score, stance and `retrieved_at`. It is skipped, with a
stated reason, when `OFFLINE_MODE=true` or no claims were found.

### 2.4 Document engine (`document`, heuristic, v1.0.0, Phase 2)

PDF → structure scan (JavaScript, launch actions, embedded files; incremental saves via `%%EOF` count) →
metadata (producer/creator, creation/modification dates) → text per page (page cap `MAX_PDF_PAGES`) → OCR
for pages with no text layer → document type (invoice, receipt, bank statement, contract, certificate,
government, other) → fields (invoice number, dates, subtotal/tax/total, GSTIN, PAN, IFSC) → consistency
(totals, due vs. issue date, future dates, invoice number reused on a different file by the same owner).
All findings are `document_media` signals phrased as **potential manipulation indicators**. Extracted text
goes on to the text, URL and evidence engines; transactional documents skip message-scam and claim checks.

### 2.5 Image engine (`image`, heuristic, v1.0.0, Phase 2)

Decode with a pixel cap (decompression-bomb guard) → EXIF (software, camera, dates) → OCR with per-word
boxes and confidence → extracted text to the text engine. Pixel forensics are Phase 3 and listed as not
performed on every image result.

## 3. Explanation layer

Deterministic. It builds the summary sentence, the top signals and the
recommended actions (1.x per-category safety guidance, plus document-specific
guidance) from the risk assessment. When an LLM provider is configured, a
grounded interpretation is added beside it: findings-only prompt, validated
citations, no score changes. See [RAG.md](RAG.md#grounded-interpretation).

## 4. Planned engines

| Engine | Phase | Approach |
|---|---|---|
| PDF tables | 3 | Table extraction to check line items against the subtotal |
| Image forensics | 3 | EXIF, ELA / JPEG ghosts, copy-move (ORB keypoints), heatmap |
| Image synthetic media | 3 | Face detect → align → classifier (EfficientNet/ViT) with calibrated confidence and model version |
| Audio | 3 | VAD → Whisper transcript → ECAPA embeddings → synthetic-speech classifier → text engine on the transcript |
| Video | 3 | Chunked frame sampling (never whole-file in memory), scene cuts, per-frame faces, audio track → audio engine, timeline |
| Transactions | 4 | Feature pipeline (velocity, deviation, rolling stats) → Isolation Forest (unsupervised, no labels needed); graph of shared devices and merchants |
| QR | 4 | Decode (OpenCV `QRCodeDetector`) → URL engine / UPI payload parsing; never auto-navigate |
| Fusion | 5 | Only the modalities present; learned fusion only once labelled data exists |
| Agents | 5 | LangGraph with per-agent tool allowlists; engines above become tools |

## 5. What we will not do

- Show model metrics that were not measured on a named evaluation set.
- Label a document "forged" or media "deepfake". Output is framed as
  *potential manipulation indicators* with a confidence.
- Fill a missing provider with invented results. A provider that is down is
  reported as "Evidence unavailable from this provider."
