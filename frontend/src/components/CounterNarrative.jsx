import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Copy, Check, Globe } from 'lucide-react';

export default function CounterNarrative({ narrative }) {
  const { t, i18n } = useTranslation();
  const [copiedLang, setCopiedLang] = useState(null);

  if (!narrative) return null;

  const languages = [
    { code: 'en', label: 'English', text: narrative.summary_en },
    { code: 'hi', label: 'हिंदी', text: narrative.summary_hi },
    { code: 'ta', label: 'தமிழ்', text: narrative.summary_ta },
  ];

  const [activeLang, setActiveLang] = useState(i18n.language || 'en');

  const handleCopy = async (text, lang) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedLang(lang);
      setTimeout(() => setCopiedLang(null), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  const activeText = languages.find(l => l.code === activeLang)?.text || narrative.summary_en;

  return (
    <div className="glass-card overflow-hidden">
      {/* Header with language tabs */}
      <div className="flex items-center justify-between border-b border-white/5 px-5 py-3">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-brand-400" />
          <span className="text-sm font-semibold text-white/70">{t('report.counter_narrative')}</span>
        </div>

        <div className="flex items-center gap-1 bg-white/5 rounded-lg p-0.5">
          {languages.map(({ code, label }) => (
            <button
              key={code}
              onClick={() => setActiveLang(code)}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all duration-200 ${
                activeLang === code
                  ? 'bg-brand-500 text-white shadow-sm'
                  : 'text-white/40 hover:text-white/70'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-5">
        <div className="relative">
          <p className="text-white/80 text-sm leading-relaxed whitespace-pre-wrap">
            {activeText || 'No counter-narrative available for this language.'}
          </p>

          {activeText && (
            <button
              onClick={() => handleCopy(activeText, activeLang)}
              className="absolute top-0 right-0 p-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors group"
              title={t('report.copy')}
            >
              {copiedLang === activeLang ? (
                <Check className="w-4 h-4 text-emerald-400" />
              ) : (
                <Copy className="w-4 h-4 text-white/30 group-hover:text-white/60" />
              )}
            </button>
          )}
        </div>

        {/* Sources cited */}
        {narrative.sources_cited && narrative.sources_cited.length > 0 && (
          <div className="mt-4 pt-4 border-t border-white/5">
            <p className="text-xs font-semibold text-white/30 uppercase tracking-wider mb-2">
              {t('report.sources')} ({narrative.sources_cited.length})
            </p>
            <div className="flex flex-wrap gap-2">
              {narrative.sources_cited.map((url, idx) => {
                let domain = '';
                try { domain = new URL(url).hostname.replace('www.', ''); } catch { domain = url; }
                return (
                  <a
                    key={idx}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1 rounded-full bg-white/5 border border-white/5 text-xs text-brand-400/70 hover:text-brand-300 hover:border-brand-500/30 transition-all"
                  >
                    {domain}
                  </a>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
