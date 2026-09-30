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
| Scam and phishing | 1.x `message_scam` + `email_fraud` detectors | Hinglish-aware, category-specific |
| Manipulation | 1.x deception register (`urgency`, `authority`, `suppression`, `engagement_bait`, `financial`, …) | |
| Prompt injection | Patterns aimed at AI systems ("ignore previous instructions", "reveal your system prompt") | Flagged as `info`. Such text is data here, never instructions |

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
0.8 without an exact match) and **high-entropy host**.

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

### 2.3 Evidence engine (`evidence`, retrieval, v1.0.0)

For each extracted claim (at most `MAX_CLAIMS_PER_SUBMISSION`), it runs the
1.x retrieval stack: multi-provider search → credibility ranking → NLI
stance → verdict. The verdict maps to the spec vocabulary:

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

## 3. Explanation layer

Deterministic. It builds the summary sentence, the top signals and the
recommended actions (1.x per-category safety guidance) from the risk
assessment. `explanation.llm` is `null` in Phase 1. When an LLM provider is
configured (Phase 2), it receives only structured findings, never raw input
as instructions. Its output must cite signal codes or source ids that
exist, or it is discarded.

## 4. Planned engines

| Engine | Phase | Approach |
|---|---|---|
| Document (PDF) | 2 | pypdf metadata/text → OCR fallback → table extraction → numeric consistency (totals, dates, duplicate invoice IDs) |
| OCR | 2 | Tesseract / PaddleOCR behind `BaseOCRProvider`; boxes and confidences |
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
