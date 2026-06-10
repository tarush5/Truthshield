import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { ArrowLeft, Share2, Clock, Globe, AlertTriangle, CheckCircle, BarChart3, Copy, Check, Download, ExternalLink } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import TrustGauge from '../components/TrustGauge';
import ClaimTable from '../components/ClaimTable';
import CounterNarrative from '../components/CounterNarrative';
import { API_BASE } from '../config';

const COMPONENT_COLORS = {
  text: '#3b93ff',
  deepfake: '#f97316',
  voice: '#8b5cf6',
  ai_content: '#06b6d4',
};

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 },
};

export default function Report() {
  const { id } = useParams();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchReport();
  }, [id]);

  const fetchReport = async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch(`${API_BASE}/report/${id}`, { headers });
      if (!res.ok) throw new Error('Report not found');
      const data = await res.json();
      setReport(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleShare = async () => {
    const url = window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  };

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 flex items-center justify-center min-h-[50vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-brand-500/30 border-t-brand-500 rounded-full animate-spin" />
          <p className="text-white/40">Loading report...</p>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="max-w-5xl mx-auto px-4 text-center py-20">
        <AlertTriangle className="w-16 h-16 text-amber-400/50 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-white/70 mb-2">Report Not Found</h2>
        <p className="text-white/40 mb-6">{error || 'The requested report does not exist.'}</p>
        <Link to="/analyze" className="btn-primary inline-flex items-center gap-2">
          <ArrowLeft className="w-4 h-4" /> Back to Analyze
        </Link>
      </div>
    );
  }

  const componentData = Object.entries(report.credibility?.component_scores || {}).map(([key, value]) => ({
    name: key.charAt(0).toUpperCase() + key.slice(1).replace('_', ' '),
    score: value,
    color: COMPONENT_COLORS[key] || '#64748b',
  }));

  const explanationText = report.explanation
    ? report.explanation[`text_${i18n.language}`] || report.explanation.text_en
    : null;

  // Verdict color helper
  const getVerdictStyle = (verdict) => {
    const v = (verdict || '').toUpperCase();
    if (v.includes('TRUE') || v.includes('AUTHENTIC')) return 'badge-success';
    if (v.includes('FALSE')) return 'badge-danger';
    if (v.includes('MISLEADING')) return 'badge-warning';
    return 'badge-info';
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <motion.div {...fadeUp} className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-white/40 hover:text-white transition-all"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold font-display gradient-text">{t('report.title') || 'Analysis Report'}</h1>
            <div className="flex items-center gap-3 mt-1 flex-wrap">
              {report.processing_time_seconds && (
                <span className="flex items-center gap-1.5 text-xs text-white/30">
                  <Clock className="w-3 h-3" />
                  {report.processing_time_seconds}s
                </span>
              )}
              <span className="flex items-center gap-1.5 text-xs text-white/30">
                <Globe className="w-3 h-3" />
                {t(`languages.${report.language}`) || report.language || 'en'}
              </span>
              <span className="badge-info text-xs">{report.content_type}</span>
              <span className={`${getVerdictStyle(report.credibility?.verdict)} text-xs`}>
                {report.credibility?.verdict}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button onClick={handleShare} className="btn-secondary flex items-center gap-2 text-sm">
            {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Share2 className="w-4 h-4" />}
            {copied ? 'Copied!' : 'Share'}
          </button>
        </div>
      </motion.div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Trust Score */}
        <div className="lg:col-span-1 space-y-6">
          {/* Trust Gauge */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-8 flex flex-col items-center"
          >
            <h2 className="section-label mb-6">{t('report.trust_score') || 'Trust Score'}</h2>
            <TrustGauge score={report.credibility?.trust_score || 50} size={180} />
          </motion.div>

          {/* Component Breakdown */}
          {componentData.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="glass-card p-6"
            >
              <h2 className="section-label mb-4">{t('report.credibility') || 'Component Scores'}</h2>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={componentData} layout="vertical" margin={{ left: 0, right: 10, top: 5, bottom: 5 }}>
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: '#ffffff30', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" tick={{ fill: '#ffffff60', fontSize: 12 }} axisLine={false} tickLine={false} width={80} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', color: '#fff' }}
                    formatter={(val) => [`${val.toFixed(1)}%`, 'Score']}
                  />
                  <Bar dataKey="score" radius={[0, 6, 6, 0]} barSize={20}>
                    {componentData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.color} fillOpacity={0.7} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </motion.div>
          )}

          {/* Confidence Profile */}
          {report.credibility?.confidence_profile && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25 }}
              className="glass-card p-6"
            >
              <h2 className="section-label mb-4">Confidence Profile</h2>
              <div className="space-y-3">
                {Object.entries(report.credibility.confidence_profile).map(([key, value]) => (
                  <div key={key}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-white/50 capitalize">{key.replace('_', ' ')}</span>
                      <span className="text-white/70 font-medium">{typeof value === 'number' ? `${(value * 100).toFixed(0)}%` : value}</span>
                    </div>
                    {typeof value === 'number' && (
                      <div className="progress-bar">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${value * 100}%` }}
                          transition={{ duration: 1, delay: 0.5 }}
                          className="progress-fill bg-gradient-to-r from-brand-500 to-cyan-500"
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </div>

        {/* Right Column: Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Explanation */}
          {explanationText && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
              className="glass-card p-6"
            >
              <h2 className="section-label mb-3">{t('report.explanation') || 'AI Explanation'}</h2>
              <p className="text-white/80 text-sm leading-relaxed">{explanationText}</p>
            </motion.div>
          )}

          {/* Original Content */}
          {report.original_text && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="glass-card p-6"
            >
              <h2 className="section-label mb-3">Original Content</h2>
              <div className="relative">
                <p className="text-white/60 text-sm leading-relaxed max-h-40 overflow-y-auto pr-2">
                  {report.original_text}
                </p>

                {/* Inconsistency highlights */}
                {report.inconsistencies && report.inconsistencies.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-white/5">
                    <p className="text-xs font-semibold text-amber-400/70 uppercase tracking-wider mb-2">
                      ⚠ {t('report.inconsistencies') || 'Inconsistencies'} ({report.inconsistencies.length})
                    </p>
                    <div className="space-y-2">
                      {report.inconsistencies.map((inc, idx) => (
                        <motion.div
                          key={idx}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.3 + idx * 0.1 }}
                          className="flex items-start gap-2 text-sm"
                        >
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                          <span className="text-white/50">{inc.reason}</span>
                          <span className={`badge text-[10px] ${
                            inc.severity === 'high' ? 'badge-danger' : inc.severity === 'medium' ? 'badge-warning' : 'badge-info'
                          }`}>
                            {inc.severity}
                          </span>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {/* Risk Factors */}
          {report.credibility?.risk_factors && report.credibility.risk_factors.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25 }}
              className="glass-card p-6"
            >
              <h2 className="section-label mb-3">Risk Factors</h2>
              <div className="flex flex-wrap gap-2">
                {report.credibility.risk_factors.map((risk, idx) => (
                  <span key={idx} className="px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/15 text-red-400 text-xs font-medium">
                    {risk}
                  </span>
                ))}
              </div>
            </motion.div>
          )}

          {/* Claim Verification */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <h2 className="section-label mb-4">{t('report.claims') || 'Claim Verification'}</h2>
            <ClaimTable claims={report.claims} />
          </motion.div>

          {/* Counter-Narrative */}
          {report.counter_narrative && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.35 }}
            >
              <CounterNarrative narrative={report.counter_narrative} />
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
