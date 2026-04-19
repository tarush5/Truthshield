import React from 'react';
import { useTranslation } from 'react-i18next';
import { CheckCircle, XCircle, AlertTriangle, HelpCircle, ExternalLink } from 'lucide-react';

const verdictConfig = {
  TRUE: { icon: CheckCircle, color: '#10b981', bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.2)' },
  FALSE: { icon: XCircle, color: '#ef4444', bg: 'rgba(239,68,68,0.1)', border: 'rgba(239,68,68,0.2)' },
  MISLEADING: { icon: AlertTriangle, color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.2)' },
  UNVERIFIED: { icon: HelpCircle, color: '#8b5cf6', bg: 'rgba(139,92,246,0.1)', border: 'rgba(139,92,246,0.2)' },
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
                  {cv.evidence.slice(0, 3).map((ev, eIdx) => (
                    <a
                      key={eIdx}
                      href={ev.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-start gap-2 group text-sm"
                    >
                      <ExternalLink className="w-3.5 h-3.5 text-brand-400 flex-shrink-0 mt-0.5 opacity-50 group-hover:opacity-100 transition-opacity" />
                      <div>
                        <span className="text-brand-400/80 group-hover:text-brand-300 transition-colors">
                          {ev.title || ev.url}
                        </span>
                        {ev.snippet && (
                          <p className="text-white/30 text-xs mt-0.5 line-clamp-1">{ev.snippet}</p>
                        )}
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
