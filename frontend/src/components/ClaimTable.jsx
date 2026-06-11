import React from 'react';
import { useTranslation } from 'react-i18next';
import { CheckCircle, XCircle, AlertTriangle, HelpCircle, ExternalLink } from 'lucide-react';

const verdictConfig = {
  TRUE: { icon: CheckCircle, color: '#10b981', bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.2)' },
  VERIFIED: { icon: CheckCircle, color: '#10b981', bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.2)' },
  'LIKELY TRUE': { icon: CheckCircle, color: '#34d399', bg: 'rgba(52,211,153,0.1)', border: 'rgba(52,211,153,0.2)' },
  'PARTIALLY TRUE': { icon: AlertTriangle, color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.2)' },
  FALSE: { icon: XCircle, color: '#ef4444', bg: 'rgba(239,68,68,0.1)', border: 'rgba(239,68,68,0.2)' },
  'LIKELY FALSE': { icon: XCircle, color: '#f87171', bg: 'rgba(248,113,113,0.1)', border: 'rgba(248,113,113,0.2)' },
  MISLEADING: { icon: AlertTriangle, color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.2)' },
  'MIXED EVIDENCE': { icon: AlertTriangle, color: '#fbbf24', bg: 'rgba(251,191,36,0.1)', border: 'rgba(251,191,36,0.2)' },
  UNVERIFIED: { icon: HelpCircle, color: '#8b5cf6', bg: 'rgba(139,92,246,0.1)', border: 'rgba(139,92,246,0.2)' },
  'INSUFFICIENT EVIDENCE': { icon: HelpCircle, color: '#a78bfa', bg: 'rgba(167,139,250,0.1)', border: 'rgba(167,139,250,0.2)' },
};

export default function ClaimTable({ claims = [] }) {
  const { t } = useTranslation();

  if (!claims || claims.length === 0) {
    return (
      <div className="glass-card p-8 text-center">
        <HelpCircle className="w-12 h-12 text-white/20 mx-auto mb-3" />
        <p className="text-white/40">{t('report.no_claims')}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {claims.map((cv, idx) => {
        const verdict = cv.verdict || 'UNVERIFIED';
        const config = verdictConfig[verdict] || verdictConfig.UNVERIFIED;
        const Icon = config.icon;

        const supportingSources = cv.evidence ? cv.evidence.filter(e => (e.stance || '').toUpperCase() === 'SUPPORTS') : [];
        const refutingSources = cv.evidence ? cv.evidence.filter(e => (e.stance || '').toUpperCase() === 'REFUTES') : [];

        return (
          <div
            key={idx}
            className="glass-card overflow-hidden transition-all duration-300 hover:bg-white/[0.07]"
            style={{ borderColor: config.border }}
          >
            {/* Claim Header */}
            <div className="flex items-start gap-4 p-5">
              <div
                className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center mt-0.5"
                style={{ backgroundColor: config.bg }}
              >
                <Icon className="w-5 h-5" style={{ color: config.color }} />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-xs font-semibold text-white/30 uppercase tracking-wider">
                    {t('report.claim')} #{idx + 1}
                  </span>
                  <span
                    className="px-2.5 py-0.5 rounded-full text-xs font-bold"
                    style={{ color: config.color, backgroundColor: config.bg, border: `1px solid ${config.border}` }}
                  >
                    {t(`verdicts.${verdict}`)}
                  </span>
                  {cv.confidence > 0 && (
                    <span className="text-xs text-white/30">
                      {Math.round(cv.confidence * 100)}% confident
                    </span>
                  )}
                  {supportingSources.length > 0 && (
                    <span className="text-xs text-emerald-400 font-medium">
                      • Supported by {supportingSources.length} source{supportingSources.length > 1 ? 's' : ''}
                    </span>
                  )}
                  {refutingSources.length > 0 && (
                    <span className="text-xs text-rose-400 font-medium">
                      • Contradicted by {refutingSources.length} source{refutingSources.length > 1 ? 's' : ''}
                    </span>
                  )}
                </div>

                <p className="text-white/90 text-sm leading-relaxed">{cv.claim?.text || cv.claim}</p>

                {cv.reasoning && (
                  <p className="mt-3 text-white/50 text-sm leading-relaxed border-l-2 pl-3"
                     style={{ borderColor: config.border }}>
                    {cv.reasoning}
                  </p>
                )}
              </div>
            </div>

            {/* Evidence */}
            {cv.evidence && cv.evidence.length > 0 && (
              <div className="border-t border-white/5 px-5 py-3 bg-white/[0.02]">
                <p className="text-xs font-semibold text-white/30 uppercase tracking-wider mb-2">
                  {t('report.evidence')}
                </p>
                <div className="space-y-2">
                  {cv.evidence.slice(0, 5).map((ev, eIdx) => {
                    const stance = (ev.stance || 'NEUTRAL').toUpperCase();
                    let stanceConfig = { label: 'NEUTRAL', color: '#94a3b8', bg: 'rgba(148,163,184,0.1)', border: 'rgba(148,163,184,0.2)' };
                    if (stance === 'SUPPORTS') {
                      stanceConfig = { label: 'SUPPORTS', color: '#10b981', bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.2)' };
                    } else if (stance === 'REFUTES') {
                      stanceConfig = { label: 'REFUTES', color: '#ef4444', bg: 'rgba(239,68,68,0.1)', border: 'rgba(239,68,68,0.2)' };
                    } else if (stance === 'INSUFFICIENT') {
                      stanceConfig = { label: 'INSUFFICIENT', color: '#a78bfa', bg: 'rgba(167,139,250,0.1)', border: 'rgba(167,139,250,0.2)' };
                    }

                    return (
                      <div key={eIdx} className="flex items-start gap-3 py-2 border-b border-white/[0.03] last:border-0">
                        <ExternalLink className="w-3.5 h-3.5 text-brand-400 flex-shrink-0 mt-1 opacity-50" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap mb-1">
                            <a
                              href={ev.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-brand-400/90 hover:text-brand-300 font-medium transition-colors text-sm hover:underline truncate"
                            >
                              {ev.title || ev.url}
                            </a>
                            <span
                              className="px-1.5 py-0.2 rounded text-[9px] font-extrabold tracking-wider uppercase border"
                              style={{
                                color: stanceConfig.color,
                                backgroundColor: stanceConfig.bg,
                                borderColor: stanceConfig.border,
                              }}
                            >
                              {stanceConfig.label}
                            </span>
                            {ev.source_score > 0 && (
                              <span className="text-[10px] text-white/30">
                                Credibility: {Math.round(ev.source_score * 100)}%
                              </span>
                            )}
                          </div>
                          {ev.snippet && (
                            <p className="text-white/40 text-xs leading-relaxed">{ev.snippet}</p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
