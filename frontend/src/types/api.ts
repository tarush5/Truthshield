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

export type InvestigationType = 'text' | 'url' | 'message' | 'email';

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
  features: Record<string, number>;
  explanation: {
    summary: string;
    top_signals: { code: string; title: string; points: number; provenance: Provenance }[];
    method: string;
    llm: string | null;
    llm_status: string;
    llm_note: string;
  };
  uncertainties: string[];
  recommended_actions: Guidance;
  input: { type: string; sha256: string; size_bytes: number; redacted: string; redactions: { kind: string; count: number }[]; is_demo: boolean };
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
  input: { kind: string; sha256: string; size_bytes: number; content: string | null; redacted: string | null };
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
