# TruthShield — Architecture Document

## Component Interaction Diagram

```
                         ┌─────────────────────┐
                         │     User Input       │
                         │ (text/img/audio/vid) │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │   FastAPI Gateway    │
                         │  routes.py + ws.py   │
                         │  Rate Limit + CORS   │
                         └──────────┬──────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │   MULTIMODAL PREPROCESSOR      │
                    ├───────────────────────────────┤
                    │ text_processor   → langdetect  │
                    │ image_processor  → Tesseract   │
                    │                    + BLIP-2     │
                    │ audio_processor  → Whisper      │
                    │                    + ECAPA-TDNN │
                    │ video_processor  → OpenCV       │
                    │                    + ffmpeg     │
                    │ url_scraper      → BS4          │
                    ├───────────────────────────────┤
                    │ Output: ContentPacket           │
                    └───────────────┬───────────────┘
                                    │
               ┌────────────────────▼────────────────────┐
               │    SOCIAL INGESTION & ENRICHMENT        │
               ├─────────────────────────────────────────┤
               │  twitter_monitor  → Tweepy (Filtered)   │
               │  reddit_monitor   → PRAW                │
               │  telegram_monitor → Telethon            │
               │  youtube_monitor  → Data API v3          │
               │  mastodon_monitor → Public REST API      │
               │  discord_monitor  → Bot REST API         │
               │  whatsapp_tipline → Twilio Webhook       │
               │  social_enricher  → Virality/Crisis flag│
               └────────────────────┬────────────────────┘
                                    │
              ┌─────────────────────▼─────────────────────┐
              │            DETECTION LAYER                 │
              ├───────────────────────────────────────────┤
              │                                           │
              │  text_classifier ──────► XLM-RoBERTa      │
              │    → label: fake/real/misleading           │
              │    → confidence + explanation_tokens       │
              │                                           │
              │  deepfake_detector ────► EfficientNet-B4   │
              │    → face detection (Haar Cascade)         │
              │    → per-frame scoring → aggregation       │
              │                                           │
              │  voice_clone_detector ─► ECAPA-TDNN        │
              │    → speaker embedding analysis            │
              │    → spectral anomaly scoring              │
              │                                           │
              │  ai_content_detector ──► Binoculars            │
              │    → zero-shot LLM detection using GPT-2/Falcon│
              │    → SynthID pre-filter + C2PA watermark       │
              │                                           │
              │  credibility_scorer ───► Weighted Fusion    │
              │    → text=0.35, deepfake=0.25              │
              │    → voice=0.20, ai_content=0.20           │
              │    → Output: trust_score (0-100)           │
              └─────────────────────┬─────────────────────┘
                                    │
              ┌─────────────────────▼─────────────────────┐
              │       FACT VERIFICATION PIPELINE           │
              ├───────────────────────────────────────────┤
              │                                           │
              │  claim_extractor ─► spaCy NER              │
              │    → extract verifiable claims              │
              │    → support multilingual (xx_ent_wiki_sm) │
              │                                           │
              │  evidence_retriever ─► Multi-source         │
              │    → NewsAPI / GDELT (global news)         │
              │    → Google CSE (Indian news config)       │
              │    → RSS Aggregator + Deduplicator         │
              │    → Wikipedia API (entity verification)   │
              │    → PIB India RSS (official statements)   │
              │                                           │
              │  source_ranker ─► Domain credibility DB     │
              │    → .gov.in = 0.9, news = 0.7             │
              │    → unknown = 0.3, disinfo = 0.0          │
              │                                           │
              │  verdict_engine ─► Claude API               │
              │    → structured JSON verdict per claim      │
              │    → TRUE / FALSE / MISLEADING / UNVERIFIED│
              └─────────────────────┬─────────────────────┘
                                    │
              ┌─────────────────────▼─────────────────────┐
              │        COUNTER-RESPONSE ENGINE             │
              ├───────────────────────────────────────────┤
              │                                           │
              │  multilingual_explainer ─► Claude API      │
              │    → Simple explanations in en/hi/ta       │
              │    → Under 100 words, no jargon            │
              │                                           │
              │  inconsistency_highlighter ─► Claude API   │
              │    → Identify problematic text spans        │
              │    → GradCAM heatmap for images            │
              │                                           │
              │  counter_narrative_generator ─► Claude API  │
              │    → Evidence-grounded counter-narratives   │
              │    → Inline source citations                │
              │    → Output in all 3 languages              │
              └─────────────────────┬─────────────────────┘
                                    │
                         ┌──────────▼──────────┐
                         │   AnalysisReport     │
                         │  (JSON response)     │
                         └──────────┬──────────┘
                                    │
              ┌─────────────────────▼─────────────────────┐
              │              DELIVERY CHANNELS             │
              │                                           │
              │  🌐 React Dashboard (web)                  │
              │  📱 WhatsApp Bot (Twilio webhook)          │
              │  🔌 Chrome Extension (Manifest V3)         │
              └───────────────────────────────────────────┘
```

## Data Flow Description

### 1. Input Ingestion
User submits content via any channel (web, WhatsApp, extension). The API gateway normalizes the input into a multipart form request.

### 2. Preprocessing
The preprocessor detects the content type and routes to the appropriate handler:
- **Text**: Language detection → cleaning → ContentPacket
- **Image**: Tesseract OCR → BLIP-2 caption → ContentPacket  
- **Audio**: Whisper transcription → speaker embedding → ContentPacket
- **Video**: OpenCV keyframes + ffmpeg audio extraction → ContentPacket
- **URL**: BeautifulSoup scraping → article text + og:image → ContentPacket

### 3. Detection
All applicable detectors run on the ContentPacket:
- Text classifier produces fake/real/misleading labels
- Deepfake detector analyzes face regions in image frames
- Voice clone detector checks for synthetic speech markers
- AI content detector measures text perplexity

The credibility scorer fuses all detector outputs with calibrated weights.

### 4. Fact Verification
Claims are extracted from text using NER, then each claim is:
1. Searched across multiple evidence sources
2. Evidence is ranked by source credibility
3. Claude evaluates each claim against evidence
4. Structured verdicts are produced per claim

### 5. Counter-Response
For flagged content (trust_score < 75):
- Simple explanations generated in 3 languages
- Inconsistent spans identified in original text
- Evidence-grounded counter-narrative produced

### 6. Delivery
The complete AnalysisReport is returned to the requesting channel with appropriate formatting.

## Model Choices & Justification

| Model | Justification |
|-------|---------------|
| **XLM-RoBERTa** | Best multilingual transformer; supports 100+ languages including Hindi and Tamil |
| **EfficientNet-B4** | Optimal accuracy/efficiency trade-off for face forgery detection |
| **ECAPA-TDNN** | State-of-the-art speaker verification; robust to recording conditions |
| **GPT-2** | Widely available; perplexity scoring reliably detects AI-generated text |
| **Binoculars** | State-of-the-art zero-shot AI detection without needing an explicit classifier training set |
| **Whisper** | Best open-source STT; excellent multilingual recognition |
| **Claude claude-sonnet-4-6** | Strong structured reasoning; reliable JSON output; multilingual generation; uses crisis flags for thresholding |
| **spaCy** | Fast, production-grade NLP; multilingual NER models available |

## Scalability Notes

### Horizontal Scaling
- **Backend**: Stateless FastAPI workers behind a load balancer
- **Redis Cache**: Cache analysis results by content hash (TTL: 24h)
- **Model Workers**: Deploy heavy ML models on GPU workers via Celery/RQ
- **Database**: PostgreSQL with read replicas for report retrieval

### Performance Optimizations
- Lazy model loading (models loaded on first use)
- Async I/O for external API calls (SerpAPI, Claude)
- WebSocket streaming for real-time progress
- Content hash deduplication to avoid re-analyzing identical content

### Recommended Production Setup
```
                    ┌─────────────┐
                    │ Nginx / CDN │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Load Balancer│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         ┌────▼────┐ ┌────▼────┐ ┌────▼────┐
         │ API Pod │ │ API Pod │ │ API Pod │
         └────┬────┘ └────┬────┘ └────┬────┘
              │            │            │
         ┌────▼────────────▼────────────▼────┐
         │           Redis Cluster            │
         └────────────────┬──────────────────┘
                          │
         ┌────────────────▼──────────────────┐
         │    PostgreSQL (Primary + Replica)   │
         └────────────────────────────────────┘
```
