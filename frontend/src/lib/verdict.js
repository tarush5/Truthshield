import {
  ShieldCheck, CheckCircle2, AlertTriangle, XCircle, HelpCircle, Scale,
} from 'lucide-react';

/**
 * One place that knows what a verdict looks like.
 *
 * The backend emits eight verdict strings and the UI rendered them with ad-hoc
 * `includes('TRUE')` string tests, so "INSUFFICIENT EVIDENCE" and "PARTIALLY
 * TRUE" picked up styling meant for something else and every surface disagreed
 * about which colour a verdict was.
 *
 * Each entry carries an icon as well as a colour: status colour never carries
 * meaning on its own.
 */
const VERDICTS = {
  'VERIFIED': {
    tone: 'good', icon: ShieldCheck, badge: 'badge-success',
    headline: 'Verified',
    gist: 'Credible sources confirm this.',
  },
  'TRUE': {
    tone: 'good', icon: ShieldCheck, badge: 'badge-success',
    headline: 'True',
    gist: 'Credible sources confirm this.',
  },
  'LIKELY TRUE': {
    tone: 'good', icon: CheckCircle2, badge: 'badge-success',
    headline: 'Likely true',
    gist: 'The weight of evidence supports this.',
  },
  'PARTIALLY TRUE': {
    tone: 'warning', icon: Scale, badge: 'badge-warning',
    headline: 'Partially true',
    gist: 'Parts hold up; parts do not.',
  },
  'MIXED EVIDENCE': {
    tone: 'warning', icon: Scale, badge: 'badge-warning',
    headline: 'Mixed evidence',
    gist: 'Credible sources disagree.',
  },
  'MISLEADING': {
    tone: 'serious', icon: AlertTriangle, badge: 'badge-warning',
    headline: 'Misleading',
    gist: 'Technically sourced, but framed to mislead.',
  },
  'LIKELY FALSE': {
    tone: 'critical', icon: AlertTriangle, badge: 'badge-danger',
    headline: 'Likely false',
    gist: 'The weight of evidence contradicts this.',
  },
  'FALSE': {
    tone: 'critical', icon: XCircle, badge: 'badge-danger',
    headline: 'False',
    gist: 'Credible sources contradict this.',
  },
  'INSUFFICIENT EVIDENCE': {
    tone: 'neutral', icon: HelpCircle, badge: 'badge-info',
    headline: 'Not enough evidence',
    gist: 'Nothing found that settles this either way.',
  },
  'UNVERIFIED': {
    tone: 'neutral', icon: HelpCircle, badge: 'badge-info',
    headline: 'Unverified',
    gist: 'Nothing found that settles this either way.',
  },
};

const FALLBACK = VERDICTS['UNVERIFIED'];

/** CSS variable name per tone, so callers can style without a colour literal. */
export const TONE_VAR = {
  good: '--c-good',
  warning: '--c-warning',
  serious: '--c-serious',
  critical: '--c-critical',
  neutral: '--c-ink-muted',
};

export const TONE_TEXT_VAR = {
  good: '--c-good-text',
  warning: '--c-warning-text',
  serious: '--c-serious',
  critical: '--c-critical-text',
  neutral: '--c-ink-secondary',
};

export function getVerdict(verdict) {
  if (!verdict) return FALLBACK;
  return VERDICTS[String(verdict).toUpperCase().trim()] || FALLBACK;
}

/** `rgb(var(--token) / alpha)` for a verdict's tone — marks, fills, rings. */
export function toneColor(verdict, alpha = 1) {
  const v = TONE_VAR[getVerdict(verdict).tone];
  return alpha === 1 ? `rgb(var(${v}))` : `rgb(var(${v}) / ${alpha})`;
}

/** The lighter step, for small text that must clear 4.5:1. */
export function toneTextColor(verdict) {
  return `rgb(var(${TONE_TEXT_VAR[getVerdict(verdict).tone]}))`;
}

/**
 * Trust score bands. Kept aligned with the backend's verdict calibration in
 * ResultAggregator (VERIFIED ≥85, LIKELY TRUE 65-84, PARTIALLY TRUE/MIXED
 * 45-64, LIKELY FALSE 15-44, FALSE ≤25) so the dial and the verdict label can
 * never tell the reader two different stories.
 */
export function trustBand(score) {
  if (score >= 85) return { tone: 'good', label: 'High trust' };
  if (score >= 65) return { tone: 'good', label: 'Leans credible' };
  if (score >= 45) return { tone: 'warning', label: 'Uncertain' };
  if (score >= 25) return { tone: 'critical', label: 'Leans false' };
  return { tone: 'critical', label: 'Low trust' };
}

/** Evidence stance, shown per source in the claim breakdown. */
export const STANCE = {
  SUPPORTS: { label: 'Supports', tone: 'good', icon: CheckCircle2 },
  REFUTES: { label: 'Refutes', tone: 'critical', icon: XCircle },
  NEUTRAL: { label: 'Neutral', tone: 'neutral', icon: Scale },
  INSUFFICIENT: { label: 'Off-topic', tone: 'neutral', icon: HelpCircle },
};

export function getStance(stance) {
  return STANCE[String(stance || 'NEUTRAL').toUpperCase()] || STANCE.NEUTRAL;
}

/**
 * Source credibility tiers, mirroring backend/config.py.
 * 0.50 is the unknown-domain default; anything below it is a demoted tier.
 */
export function sourceTier(score) {
  if (score >= 0.90) return { label: 'Authoritative', tone: 'good' };
  if (score >= 0.70) return { label: 'Reliable', tone: 'good' };
  if (score >= 0.50) return { label: 'Mixed', tone: 'warning' };
  if (score > 0) return { label: 'Low quality', tone: 'critical' };
  return { label: 'Known disinfo', tone: 'critical' };
}

export function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url || '';
  }
}
