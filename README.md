# 🛡️ TruthShield — AI Misinformation Response System

> A production-ready, multimodal AI system that detects misinformation across text, images, audio, and video — with fact-verification, counter-narrative generation, and multilingual support (English, Hindi, Tamil).

---

## 📋 Problem Statement

Misinformation spreads 6x faster than factual content online. In multilingual markets like India, false claims in Hindi, Tamil, and English go viral before fact-checkers can respond. **TruthShield** is an AI-powered system that:

- **Detects** fake news, deepfakes, voice clones, and AI-generated content
- **Verifies** claims against trusted sources in real-time
- **Generates** counter-narratives in the user's language
- **Deploys** across web, WhatsApp, and browser extension

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TruthShield Architecture                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Web UI  │  │ WhatsApp │  │ Browser  │  │  REST API │  │
│  │ (React)  │  │   Bot    │  │Extension │  │  Clients  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│       │              │             │              │         │
│       └──────────────┴─────────────┴──────────────┘         │
│                          │                                   │
│              ┌───────────▼──────────────┐                   │
│              │    FastAPI REST + WS      │                   │
│              │   /analyze  /report      │                   │
│              └───────────┬──────────────┘                   │
│                          │                                   │
│         ┌────────────────▼────────────────┐                 │
│         │    MULTIMODAL PREPROCESSOR      │                 │
│         │ Text │ Image │ Audio │ Video │ URL                │
│         └────────────────┬────────────────┘                 │
│                          │                                   │
│    ┌─────────────────────▼─────────────────────┐            │
│    │          DETECTION LAYER                   │            │
│    │ ┌───────────┐ ┌──────────┐ ┌────────────┐ │            │
│    │ │XLM-RoBERTa│ │EfficientN│ │ECAPA-TDNN  │ │            │
│    │ │Text Class.│ │Deepfake  │ │Voice Clone │ │            │
│    │ └───────────┘ └──────────┘ └────────────┘ │            │
│    │ ┌───────────┐ ┌──────────────────────────┐│            │
│    │ │GPT-2 Perp.│ │ Credibility Scorer       ││            │
│    │ │AI Content │ │ (Weighted Fusion)         ││            │
│    │ └───────────┘ └──────────────────────────┘│            │
│    └─────────────────────┬─────────────────────┘            │
│                          │                                   │
│    ┌─────────────────────▼─────────────────────┐            │
│    │     FACT VERIFICATION PIPELINE             │            │
│    │ Claims → Evidence → Verdict → Ranking      │            │
│    │ (spaCy)  (SerpAPI)  (Claude)  (Source DB)  │            │
│    └─────────────────────┬─────────────────────┘            │
│                          │                                   │
│    ┌─────────────────────▼─────────────────────┐            │
│    │      COUNTER-RESPONSE ENGINE               │            │
│    │ Explainer │ Highlighter │ Narrative Gen     │            │
│    │         (Claude API — claude-sonnet-4-20250514)       │            │
│    └─────────────────────┬─────────────────────┘            │
│                          │                                   │
│              ┌───────────▼──────────────┐                   │
│              │   PostgreSQL  │  Redis    │                   │
│              │   (Storage)   │  (Cache)  │                   │
│              └──────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- (Optional) Anthropic API key for Claude-powered features

### 1. Clone & Configure

```bash
git clone https://github.com/your-team/truthshield.git
cd truthshield
cp .env.example .env
# Edit .env with your API keys
```

### 2. Launch with Docker

```bash
docker-compose up --build
```

### 3. Access Services

| Service        | URL                        |
|----------------|----------------------------|
| Frontend       | http://localhost:3000       |
| Backend API    | http://localhost:8000       |
| API Docs       | http://localhost:8000/docs  |
| WhatsApp Bot   | http://localhost:8001       |

### Local Development (without Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

---

## 📡 API Documentation

### `POST /api/v1/analyze`
Analyze content for misinformation.

```bash
# Text analysis
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "text=India's GDP grew by 500% last quarter according to anonymous sources" \
  -F "lang=en"

# URL analysis
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "url=https://example.com/article" \
  -F "lang=en"

# File upload
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "file=@suspicious_image.jpg" \
  -F "lang=en"
```

### `GET /api/v1/report/{id}`
Retrieve a full analysis report.

```bash
curl http://localhost:8000/api/v1/report/abc123def456
```

### `POST /api/v1/feedback`
Submit user feedback on a report.

```bash
curl -X POST http://localhost:8000/api/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{"report_id": "abc123", "user_verdict": "FALSE", "comment": "This is confirmed fake"}'
```

### `GET /api/v1/stats`
Dashboard statistics.

```bash
curl http://localhost:8000/api/v1/stats
```

### `WebSocket /ws/analyze`
Real-time streaming analysis.

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/analyze');
ws.send(JSON.stringify({ text: "Content to analyze", lang: "en" }));
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

---

## 📊 Evaluation Criteria

| Criterion              | How TruthShield Addresses It                                      |
|------------------------|-------------------------------------------------------------------|
| **Multimodal Input**   | Text, image, audio, video, URL — all processed through unified pipeline |
| **Multilingual**       | Hindi, Tamil, English — detection + explanation in all 3 languages  |
| **AI Detection**       | XLM-RoBERTa, EfficientNet-B4, ECAPA-TDNN, GPT-2 perplexity       |
| **Fact Verification**  | Claim extraction → evidence retrieval → Claude-powered verdicts   |
| **Counter-Narrative**  | Grounded counter-narratives with source citations in 3 languages   |
| **Deepfake Detection** | EfficientNet-B4 on video frames with face region analysis         |
| **Voice Cloning**      | ECAPA-TDNN embeddings + spectral anomaly analysis                  |
| **Accessibility**      | Web dashboard, WhatsApp bot, Chrome extension                      |
| **Scalability**        | Docker Compose, Redis caching, horizontal scaling ready            |
| **Source Credibility** | Tiered scoring: gov=0.9, major news=0.7, unknown=0.3, disinfo=0.0 |

---

## 🔧 Tech Stack

| Component        | Technology                                    |
|------------------|-----------------------------------------------|
| Backend          | Python 3.11, FastAPI, Pydantic                |
| Frontend         | React 18, Vite, Tailwind CSS, Recharts        |
| AI Orchestrator  | Anthropic Claude (claude-sonnet-4-20250514)             |
| Text Detection   | XLM-RoBERTa (zero-shot classification)        |
| Deepfake         | EfficientNet-B4 + OpenCV                      |
| Voice Analysis   | ECAPA-TDNN (SpeechBrain) + librosa            |
| AI Detection     | GPT-2 perplexity scoring                      |
| Speech-to-Text   | OpenAI Whisper                                |
| NLP              | spaCy (multilingual NER)                      |
| OCR              | Tesseract (eng + hin + tam)                   |
| Evidence Search  | SerpAPI / DuckDuckGo / Wikipedia / PIB India  |
| Database         | PostgreSQL 16                                 |
| Cache            | Redis 7                                       |
| Deployment       | Docker Compose                                |

---

## ⚠️ Limitations & Future Work

### Current Limitations
- ML models use base/pretrained weights (no fine-tuned checkpoints included)
- Deepfake detection uses ImageNet-pretrained EfficientNet (not FaceForensics++)
- In-memory report storage (PostgreSQL integration is infrastructure-ready)
- Rate-limited by API key quotas (Anthropic, SerpAPI)

### Future Roadmap
- [ ] Fine-tune XLM-RoBERTa on LIAR + translated Hindi/Tamil datasets
- [ ] Train EfficientNet-B4 on FaceForensics++ for real deepfake detection
- [ ] Add AASIST anti-spoofing model for voice clone detection
- [ ] PostgreSQL persistence with SQLAlchemy ORM
- [ ] Redis caching for repeat URL analysis
- [ ] Kubernetes deployment with horizontal pod autoscaling
- [ ] Mobile app (React Native)
- [ ] Crowdsourced fact-checking community features
- [ ] Real-time social media monitoring (Twitter/X API)

---

## 👥 Team Setup Guide

1. Fork the repository
2. Copy `.env.example` to `.env` and add your API keys
3. Run `docker-compose up --build` for full stack
4. For development, run backend and frontend separately (see Quick Start)
5. Run tests: `cd backend && pytest tests/`

---

## 📄 License

MIT License — Built for the fight against misinformation.
