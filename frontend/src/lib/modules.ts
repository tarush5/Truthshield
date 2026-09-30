/**
 * Every capability the platform names, with its real availability.
 *
 * One list drives the landing page, the navigation and the module pages, so
 * the marketing surface can never claim more than the product does.
 */

export type Availability = 'live' | 'partial' | 'planned';

export interface Capability {
  id: string;
  title: string;
  route: string;
  image: string;
  availability: Availability;
  phase: number;
  summary: string;
  today: string[];
  planned: string[];
}

const img = (id: string) => `https://images.unsplash.com/photo-${id}?auto=format&fit=crop&w=1200&q=70`;

export const CAPABILITIES: Capability[] = [
  {
    id: 'multimodal',
    title: 'Multimodal Intelligence',
    route: '/app/investigate',
    image: img('1618005182384-a83a8bd57fbe'),
    availability: 'partial',
    phase: 3,
    summary: 'One investigation pipeline for every kind of input, with engines that declare what they handle.',
    today: ['Text, messages, emails and URLs through one audited 12-stage pipeline', 'Cross-signal scoring when a message carries a link'],
    planned: ['PDF and OCR (Phase 2)', 'Image, audio and video (Phase 3)', 'Learned multimodal fusion (Phase 5)'],
  },
  {
    id: 'fraud',
    title: 'Fraud Detection',
    route: '/app/m/fraud',
    image: img('1563986768609-322da13575f3'),
    availability: 'partial',
    phase: 4,
    summary: 'Scam categories, social-engineering tactics and impersonation — including Hinglish.',
    today: ['Scam-category detection in messages and emails', 'Sender/reply-to/display-name mismatch analysis', 'Per-category safety guidance'],
    planned: ['Transaction anomaly detection with Isolation Forest (Phase 4)', 'Transaction graph and mule-account patterns (Phase 4)'],
  },
  {
    id: 'misinformation',
    title: 'Misinformation Analysis',
    route: '/app/m/misinformation',
    image: img('1504711434969-e33886168f5c'),
    availability: 'partial',
    phase: 2,
    summary: 'Claims extracted and checked against retrieved sources — with INSUFFICIENT_EVIDENCE as a real answer.',
    today: ['Claim extraction', 'Multi-provider retrieval, credibility ranking and NLI stance', 'Manipulation-register signals'],
    planned: ['pgvector hybrid retrieval with reranking (Phase 2)', 'Claim verification workspace (Phase 2)'],
  },
  {
    id: 'deepfake',
    title: 'Deepfake Detection',
    route: '/app/m/deepfake',
    image: img('1500648767791-00dcc994a43e'),
    availability: 'planned',
    phase: 3,
    summary: 'Synthetic-media signals for faces, voices and video — reported as signals with a model version, never as proof.',
    today: [],
    planned: ['Face detection → alignment → calibrated classifier', 'Frame timeline for video', 'Synthetic-speech analysis for audio'],
  },
  {
    id: 'documents',
    title: 'Document Forensics',
    route: '/app/m/documents',
    image: img('1455390582262-044cdead277a'),
    availability: 'planned',
    phase: 2,
    summary: 'Invoices, statements and certificates checked for numerical and metadata inconsistencies.',
    today: [],
    planned: ['PDF text and metadata extraction with OCR fallback', 'Totals, dates and duplicate-ID consistency checks', 'OCR overlays with confidence'],
  },
  {
    id: 'url',
    title: 'URL Intelligence',
    route: '/app/url-intelligence',
    image: img('1558494949-ef010cbdcc31'),
    availability: 'live',
    phase: 1,
    summary: 'Lookalike domains, structural phishing signals, a model-ready feature vector and sandboxed page inspection.',
    today: ['Typosquat and brand-mismatch detection', 'Feature vector: entropy, digit ratio, path depth and more', 'SSRF-guarded page fetch with redirect chain'],
    planned: ['WHOIS age, certificates and reputation feeds (Phase 7)'],
  },
  {
    id: 'rag',
    title: 'Evidence-Based RAG',
    route: '/app/m/rag',
    image: img('1507842217343-583bb7270b66'),
    availability: 'partial',
    phase: 2,
    summary: 'Every factual statement traceable to a retrieved passage, with publisher, stance and retrieval time.',
    today: ['Source metadata and categories on every piece of evidence', 'Citations verified against retrieved sources'],
    planned: ['pgvector store, query expansion and reranking (Phase 2)'],
  },
  {
    id: 'xai',
    title: 'Explainable AI',
    route: '/app/investigate',
    image: img('1620712943543-bcc4688e7485'),
    availability: 'live',
    phase: 1,
    summary: 'A score you can take apart: every point attributed to a signal, with provenance and uncertainty.',
    today: ['Exact per-signal risk attribution', 'Provenance on every signal', 'Stage-by-stage audit timeline'],
    planned: ['Grounded LLM interpretation, labelled as such (Phase 2)'],
  },
  {
    id: 'security',
    title: 'Enterprise Security',
    route: '/app/m/security',
    image: img('1550751827-4bd374c3f58b'),
    availability: 'partial',
    phase: 7,
    summary: 'Built like it will be attacked: RBAC, rotating sessions, SSRF guards and audit trails.',
    today: ['Role-based access, rotating refresh tokens, lockout', 'SSRF protection, rate limits, audit logging', 'PII masking in stored excerpts and exports'],
    planned: ['OpenTelemetry, Prometheus and Grafana (Phase 7)', 'Per-role rate limits and cost tracking (Phase 7)'],
  },
];

export const MODALITIES: { label: string; availability: Availability; phase: number }[] = [
  { label: 'Text', availability: 'live', phase: 1 },
  { label: 'URL', availability: 'live', phase: 1 },
  { label: 'Email', availability: 'live', phase: 1 },
  { label: 'PDF', availability: 'planned', phase: 2 },
  { label: 'Image', availability: 'planned', phase: 3 },
  { label: 'Audio', availability: 'planned', phase: 3 },
  { label: 'Video', availability: 'planned', phase: 3 },
  { label: 'Transaction', availability: 'planned', phase: 4 },
];

export const AVAILABILITY_LABEL: Record<Availability, string> = {
  live: 'Live',
  partial: 'Partially live',
  planned: 'In development',
};

/** Sidebar modules that are not landing-page capabilities. */
export const EXTRA_MODULES: Capability[] = [
  {
    id: 'threat-intel', title: 'Threat Intelligence', route: '/app/m/threat-intel', image: '', availability: 'planned', phase: 5,
    summary: 'Suspicious domains, URLs and indicators aggregated across investigations and external feeds.',
    today: ['Every investigated URL is stored with its feature vector and signals, ready to aggregate'],
    planned: ['Indicator views with search, filter and sort (Phase 5)', 'External threat-intelligence feeds behind a provider interface (Phase 7)'],
  },
  {
    id: 'transactions', title: 'Transaction Analysis', route: '/app/m/transactions', image: '', availability: 'planned', phase: 4,
    summary: 'Unsupervised anomaly detection and relationship graphs over transaction exports.',
    today: [],
    planned: ['Reusable feature pipeline: velocity, deviation, rolling statistics', 'Isolation Forest anomaly scores with per-feature explanations', 'Customer–account–merchant–device graph'],
  },
  {
    id: 'reports', title: 'Reports', route: '/app/m/reports', image: '', availability: 'partial', phase: 6,
    summary: 'Exportable investigation reports for case files.',
    today: ['JSON and CSV export from any investigation, with redacted input and formula-safe cells'],
    planned: ['Branded PDF reports (Phase 6)'],
  },
  {
    id: 'analytics', title: 'Analytics', route: '/app/m/analytics', image: '', availability: 'partial', phase: 6,
    summary: 'Trends, risk distribution, latency percentiles and feedback quality.',
    today: ['Dashboard aggregates over real investigations: volume, levels, top factors, p50/p95/p99 latency'],
    planned: ['False-positive and false-negative tracking from analyst feedback (Phase 6)', 'Per-model performance over time (Phase 6)'],
  },
  {
    id: 'models', title: 'Model Intelligence', route: '/app/m/models', image: '', availability: 'partial', phase: 6,
    summary: 'Which engines produced each result, at which version — and measured metrics once they exist.',
    today: ['Engine registry with versions; every prediction stored with model name, version and input hash'],
    planned: ['MLflow-backed registry (Phase 6)', 'Metrics only from named evaluation datasets — none are shown until measured'],
  },
];

export const ALL_MODULES = [...CAPABILITIES, ...EXTRA_MODULES];
