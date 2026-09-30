import type { ConfidenceBand, Provenance, RiskLevel } from '@/types/api';

export function cn(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(' ');
}

export const RISK_STYLE: Record<RiskLevel, { text: string; bg: string; ring: string; hex: string; label: string }> = {
  LOW: { text: 'text-risk-low', bg: 'bg-risk-low', ring: 'ring-risk-low/40', hex: '#7fb59a', label: 'Low' },
  MEDIUM: { text: 'text-risk-medium', bg: 'bg-risk-medium', ring: 'ring-risk-medium/40', hex: '#d9b45a', label: 'Medium' },
  HIGH: { text: 'text-risk-high', bg: 'bg-risk-high', ring: 'ring-risk-high/40', hex: '#d9824e', label: 'High' },
  CRITICAL: { text: 'text-risk-critical', bg: 'bg-risk-critical', ring: 'ring-risk-critical/40', hex: '#b8474f', label: 'Critical' },
};

export const PROVENANCE_LABEL: Record<Provenance, { label: string; hint: string }> = {
  heuristic: { label: 'Heuristic', hint: 'A deterministic rule matched the input.' },
  ml_prediction: { label: 'ML model', hint: 'A trained model predicted this; it can be wrong.' },
  retrieved: { label: 'Retrieved', hint: 'Derived from external sources that were retrieved for this claim.' },
  llm: { label: 'LLM', hint: 'Written by a language model; treat as interpretation, not evidence.' },
};

export const CONFIDENCE_LABEL: Record<ConfidenceBand, string> = {
  HIGH: 'High confidence',
  MODERATE: 'Moderate confidence',
  LOW: 'Low confidence',
  VERY_LOW: 'Very low confidence',
};

export const STATUS_LABEL: Record<string, string> = {
  QUEUED: 'Queued',
  PROCESSING: 'Processing',
  ANALYZING: 'Analyzing',
  COLLECTING_EVIDENCE: 'Collecting evidence',
  CALCULATING_RISK: 'Calculating risk',
  COMPLETED: 'Completed',
  FAILED: 'Failed',
};

export const STAGE_LABEL: Record<string, string> = {
  VALIDATION: 'Validation',
  HASHING: 'Hashing',
  EXTRACTION: 'Extraction',
  CLASSIFICATION: 'Classification',
  FEATURE_EXTRACTION: 'Feature extraction',
  MODEL_ANALYSIS: 'Model analysis',
  EVIDENCE_RETRIEVAL: 'Evidence retrieval',
  CROSS_MODAL_ANALYSIS: 'Cross-modal analysis',
  RISK_ENGINE: 'Risk engine',
  EXPLANATION: 'Explanation',
  REPORT: 'Report',
  STORAGE: 'Storage',
};

export const PIPELINE_STAGES = Object.keys(STAGE_LABEL);

export const FAMILY_LABEL: Record<string, string> = {
  nlp: 'Language',
  url: 'URL',
  reputation: 'Reputation',
  behavioral: 'Behavioral',
  document_media: 'Document & media',
  evidence: 'Evidence',
};

export function humanize(value: string | null | undefined) {
  if (!value) return '—';
  const text = value.replace(/_/g, ' ').toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function formatDate(iso: string | null | undefined) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

export function relativeTime(iso: string | null | undefined, now = Date.now()) {
  if (!iso) return '—';
  const diff = (now - new Date(iso).getTime()) / 1000;
  if (Number.isNaN(diff)) return '—';
  if (diff < 45) return 'just now';
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

export function formatMs(ms: number | null | undefined) {
  if (ms === null || ms === undefined) return '—';
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export function shortHash(hash: string | null | undefined, n = 12) {
  return hash ? `${hash.slice(0, n)}…` : '—';
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * An href for an untrusted URL, or undefined.
 *
 * Source URLs come from retrieved search results; only http(s) is ever
 * rendered as a link, so a `javascript:` or `data:` URL can never execute.
 */
export function safeHref(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : undefined;
  } catch {
    return undefined;
  }
}
