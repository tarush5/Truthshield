// Wire types. Mirrors docs/API.md and truthshield/investigations/*.

export type Role = 'USER' | 'ANALYST' | 'ADMIN';

export interface User {
  id: string;
  email: string;
  org_id: string | null;
  role: Role;
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  refresh_token: string | null;
  user: User;
}

export type InvestigationType = 'text' | 'url' | 'message' | 'email' | 'document' | 'image';

export type InvestigationStatus =
  | 'QUEUED'
  | 'PROCESSING'
  | 'ANALYZING'
  | 'COLLECTING_EVIDENCE'
  | 'CALCULATING_RISK'
  | 'COMPLETED'
  | 'FAILED';

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type ConfidenceBand = 'HIGH' | 'MODERATE' | 'LOW' | 'VERY_LOW';
export type Provenance = 'heuristic' | 'ml_prediction' | 'retrieved' | 'llm';
export type Severity = 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH';
export type Family = 'nlp' | 'url' | 'reputation' | 'behavioral' | 'document_media' | 'evidence';

export interface InvestigationSummary {
  id: string;
  public_id: string;
  type: InvestigationType;
  status: InvestigationStatus;
  current_stage: string | null;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  confidence: number | null;
  confidence_band: ConfidenceBand | null;
  classification: string | null;
  language: string | null;
  excerpt: string | null;
  input_sha256: string;
  is_demo: boolean;
  processing_ms: number | null;
  error: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface TimelineEvent {
  seq: number;
  stage: string;
  status: 'completed' | 'skipped' | 'failed';
  service: string;
  message: string | null;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
}

export interface Contribution {
  code: string;
  title: string;
  family: Family;
  severity: Severity;
  provenance: Provenance;
  engine: string;
  engine_version: string;
  points: number;
  confidence: number;
  evidence: string | null;
  explanation: string;
}

export interface FamilyScore {
  score: number;
  weight: number;
  reliability: number;
  assessed: boolean;
  signals: number;
  points: number;
}

export interface RiskAssessment {
  score: number;
  level: RiskLevel;
  confidence: number;
  confidence_band: ConfidenceBand;
  represents: string;
  contributions: Contribution[];
  families: Record<string, FamilyScore>;
  config: { version: string; weights: Record<string, number>; thresholds: Record<string, number> };
  notes: string[];
}

export interface Signal {
  code: string;
  title: string;
  family: Family;
  severity: Severity;
  provenance: Provenance;
  engine: string;
  engine_version: string;
  explanation: string;
  evidence: string | null;
  confidence: number;
  weight: number;
  points: number;
}

export interface EngineSummary {
  name: string;
  version: string;
  kind: string;
  status: 'ok' | 'unavailable' | 'error' | 'not_applicable';
  duration_ms: number;
  signals: number;
  limitations: string[];
  detail: string | null;
}

export interface Source {
  title: string;
  url: string;
  publisher: string;
  category: 'PRIMARY' | 'OFFICIAL' | 'SECONDARY' | 'COMMUNITY' | 'UNKNOWN';
  credibility: number;
  stance: 'SUPPORTS' | 'REFUTES' | 'NEUTRAL' | 'OFF_TOPIC';
  passage: string;
  retrieved_at: string;
  published_at: string | null;
  document_id?: string | null;
  chunk_id?: string | null;
  content_scope?: string | null;
  scores?: SourceScores | null;
}

export interface SourceScores {
  final: number;
  components: Record<string, number>;
  semantic: number;
  keyword: number;
  rrf?: number;
  matched_by: string[];
}

export interface RetrievalDiagnostics {
  query_variants: { strategy: string; query: string }[];
  embedding: { model: string; kind: 'semantic' | 'lexical' };
  reranker: string;
  filters: Record<string, unknown>;
  local_relevant_before: number;
  live_search: 'not_needed' | 'used' | 'unavailable' | 'failed';
  live_hits: number;
  ingested: number;
  live_detail: string | null;
  candidates: number;
  passages: number;
}

export interface ClaimResult {
  id: string;
  text: string;
  entity?: string | null;
  date?: string | null;
  assessment?: 'SUPPORTED' | 'CONTRADICTED' | 'MIXED' | 'INSUFFICIENT_EVIDENCE' | 'NOT_CHECKED';
  checked?: boolean;
  confidence?: number | null;
  reasoning?: string;
  sources?: Source[];
  downgraded?: boolean;
  retrieval?: RetrievalDiagnostics | null;
}

export interface OCRWord { text: string; confidence: number; bbox: [number, number, number, number] }

export interface DocumentAnalysis {
  encrypted: boolean;
  pages?: number;
  pages_analysed?: number;
  scanned_pages?: number[];
  ocr?: { status: string; engine?: string; pages?: number[]; mean_confidence?: number | null; detail?: string };
  type?: string;
  type_scores?: Record<string, number>;
  fields?: Record<string, string | number | string[]>;
  metadata?: Record<string, string | null>;
  active_content?: string[];
  incremental_saves?: number;
  size_bytes?: number;
  text_chars?: number;
  page_previews?: string[];
}

export interface ImageAnalysis {
  width: number;
  height: number;
  format: string;
  mode: string;
  exif: Record<string, string>;
  ocr: { status: 'done' | 'unavailable'; engine?: string; languages?: string; mean_confidence?: number | null;
         text?: string; words?: OCRWord[]; detail?: string };
}

export interface PageInspection {
  final_url: string;
  redirect_chain: string[];
  status_code: number;
  content_type: string;
  title?: string | null;
  description?: string | null;
  forms?: { action: string; method: string; inputs: number; has_password: boolean }[];
  password_fields?: number;
  script_count?: number;
  external_script_hosts?: string[];
  link_count?: number;
  external_link_ratio?: number;
  iframes?: number;
}

export interface UrlIntel {
  url: string;
  host: string;
  registrable_domain: string;
  tld: string;
  closest_brand: string | null;
  features: Record<string, number>;
  signals: string[];
  page: PageInspection | null;
  fetch: { status: 'fetched' | 'skipped' | 'blocked' | 'failed'; reason: string | null; cached?: boolean };
}

export interface Guidance {
  headline: string;
  do_now: string[];
  do_not: string[];
  if_already_acted: string[];
  verify_how: string;
}

export interface InvestigationResult {
  schema_version: string;
  public_id: string;
  type: InvestigationType;
  classification: string;
  fraud_category: string;
  risk: RiskAssessment;
  signals: Signal[];
  engines: EngineSummary[];
  language: { detected: string; confidence: number; method: string; script: string; supported: boolean } | null;
  entities: Record<string, string[]>;
  intents: { intent: string; label: string; evidence: string }[];
  claims: ClaimResult[];
  url_intelligence: UrlIntel[];
  prompt_injection: string[];
  document: DocumentAnalysis | null;
  image: ImageAnalysis | null;
  features: Record<string, number>;
  explanation: {
    summary: string;
    top_signals: { code: string; title: string; points: number; provenance: Provenance }[];
    method: string;
    llm: string | null;
    llm_status: string;
    llm_note: string;
    llm_meta?: { model?: string; provider?: string; input_tokens?: number; output_tokens?: number;
                 citations?: { signals: string[]; sources: number[] } };
  };
  uncertainties: string[];
  recommended_actions: Guidance;
  input: { type: string; sha256: string; size_bytes: number; redacted: string | null; redactions: { kind: string; count: number }[];
           is_demo: boolean; filename?: string | null; mime_type?: string | null };
  processing_ms?: number;
}

export interface InvestigationDetail extends InvestigationSummary {
  timeline: TimelineEvent[];
  risk_factors: (Omit<Contribution, 'explanation'>)[];
  model_predictions: {
    model_name: string;
    model_version: string;
    model_kind: string;
    task: string;
    input_sha256: string;
    prediction: Record<string, unknown>;
    confidence: number | null;
    created_at: string;
  }[];
  input: { kind: string; sha256: string; size_bytes: number; content: string | null; redacted: string | null;
           filename?: string | null; mime_type?: string | null; has_file?: boolean };
  result: InvestigationResult | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardSummary {
  window_days: number;
  scope: 'own' | 'all';
  totals: { investigations: number; completed: number; failed: number; in_progress: number; all_time: number };
  risk_levels: Record<RiskLevel, number>;
  by_type: Record<string, number>;
  by_classification: Record<string, number>;
  average_risk: number | null;
  latency_ms: { p50: number | null; p95: number | null; p99: number | null; samples: number };
  volume: { date: string; total: number; high_or_critical: number }[];
  top_risk_factors: { code: string; title: string; count: number }[];
  recent: InvestigationSummary[];
}

export interface DemoSample {
  id: string;
  title: string;
  type: InvestigationType;
  description: string;
  content: string;
}

export interface DemoCatalogue {
  samples: DemoSample[];
  planned: { id: string; title: string; type: string; phase: number }[];
  note: string;
}

export interface EngineInfo {
  name: string;
  version: string;
  kind: string;
  describes: string;
}

export interface SystemHealth {
  status: 'ok' | 'degraded';
  version: string;
  database: boolean;
  broker: boolean;
  engines: EngineInfo[];
  risk_config_version: string;
  investigations: {
    executor: string;
    offline_mode: boolean;
    page_fetch: boolean;
    evidence_retrieval: boolean;
    completed_total: number | null;
  };
  languages: string[];
  capabilities: Record<string, boolean | string>;
}

export interface ApiErrorBody {
  error?: { code: string; message: string; request_id: string };
  detail?: unknown;
}

export interface EvidenceResult {
  chunk_id: string;
  document_id: string;
  title: string;
  url: string;
  publisher: string;
  category: Source['category'];
  credibility: number;
  content_scope: string;
  published_at: string | null;
  retrieved_at: string | null;
  passage: string;
  scores: SourceScores;
}

export interface EvidenceSearch {
  query: string;
  embedding: { model: string; kind: 'semantic' | 'lexical' };
  reranker: { name: string; learned: boolean };
  filters: Record<string, unknown>;
  results: EvidenceResult[];
}

export interface EvidenceStats {
  documents: number;
  chunks: number;
  sources: number;
  chunks_for_active_model: number;
  embedding_model: string;
  embedding_kind: 'semantic' | 'lexical';
  backend: string;
  reranker: string;
}

export interface SourceEntry {
  id: string;
  domain: string;
  name: string | null;
  category: Source['category'];
  credibility: number;
  curated: boolean;
  notes: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  documents: number;
}

export interface ClaimIndexItem {
  claim_key: string;
  text: string;
  assessment: string;
  confidence: number | null;
  source_count: number;
  investigation_id: string;
  public_id: string;
  created_at: string | null;
}
