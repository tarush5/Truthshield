import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { 
  ArrowLeft, Share2, Clock, Globe, AlertTriangle, 
  CheckCircle, BarChart3, Copy, Check, Download, ExternalLink, 
  Info, ShieldCheck, Activity, Terminal
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import TrustGauge from '../components/TrustGauge';
import ClaimTable from '../components/ClaimTable';
import CounterNarrative from '../components/CounterNarrative';
import { API_BASE } from '../config';
import InteractiveCard from '../components/InteractiveCard';


const COMPONENT_COLORS = {
  text: '#38bdf8',       // Ice blue
  deepfake: '#ef4444',   // Red/Rose
  voice: '#a78bfa',      // Aurora purple
  ai_content: '#22d3ee', // Aurora cyan
};

const fadeUp = {
  initial: { opacity: 0, y: 15 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4 },
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
      <div className="max-w-5xl mx-auto px-4 flex items-center justify-center min-h-[50vh] relative z-10">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-white/40 font-mono animate-pulse">Decompressing intelligence briefing...</p>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="max-w-xl mx-auto px-4 text-center py-20 relative z-10 space-y-6">
        <AlertTriangle className="w-12 h-12 text-amber-500/60 mx-auto" />
        <div className="space-y-2">
          <h2 className="text-lg font-bold text-white">Inference Report Unavailable</h2>
          <p className="text-xs text-white/40">{error || 'The requested verification index does not exist.'}</p>
        </div>
        <div>
          <Link to="/analyze" className="btn-secondary inline-flex items-center gap-2 text-xs py-2 px-5">
            <ArrowLeft className="w-4 h-4" /> Back to Ingestion
          </Link>
        </div>
      </div>
    );
  }

  const componentData = Object.entries(report.credibility?.component_scores || {}).map(([key, value]) => ({
    name: key.charAt(0).toUpperCase() + key.slice(1).replace('_', ' '),
    score: value,
    color: COMPONENT_COLORS[key] || '#475569',
  }));

  const explanationText = report.explanation
    ? report.explanation[`text_${i18n.language}`] || report.explanation.text_en
    : null;

  const getVerdictStyle = (verdict) => {
    const v = (verdict || '').toUpperCase();
    if (v.includes('TRUE') || v.includes('AUTHENTIC')) return 'badge-success';
    if (v.includes('FALSE')) return 'badge-danger';
    if (v.includes('MISLEADING')) return 'badge-warning';
    return 'badge-info';
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 space-y-8">
      
      {/* Header briefing controls */}
      <motion.div {...fadeUp} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-white/5">
        <div className="flex items-start gap-4">
          <button
            onClick={() => navigate(-1)}
            className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-white/40 hover:text-white transition-all border border-white/5"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-sky-400 uppercase tracking-widest font-mono">Verification Dossier</span>
              <span className="text-white/10">|</span>
              <span className="text-[10px] text-white/40 font-mono">ID: {report.id?.slice(0, 8)}...</span>
            </div>
            <h1 className="text-2xl font-bold font-display text-white mt-1">AI Intelligence Briefing</h1>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] text-white/30 font-mono flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/5">
            <Clock className="w-3.5 h-3.5" />
            {report.processing_time_seconds || 0.6}s inference
          </span>
          <button onClick={handleShare} className="btn-secondary flex items-center gap-2 text-xs py-2 px-4">
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Share2 className="w-3.5 h-3.5" />}
            {copied ? 'Copied' : 'Share Brief'}
          </button>
        </div>
      </motion.div>

      {/* Futuristic Split Screen Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Column: Verdict / Indicators (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          
          {/* Verdict and trust gauge */}
          <InteractiveCard className="border border-white/10 bg-[#030712]/40 backdrop-blur-xl">
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="p-6 space-y-6 text-center"
            >
            <div className="flex justify-between items-center text-xs border-b border-white/5 pb-3">
              <span className="font-bold text-white/40 uppercase tracking-widest">Inference Verdict</span>
              <span className={`${getVerdictStyle(report.credibility?.verdict)}`}>
                {report.credibility?.verdict || 'UNVERIFIED'}
              </span>
            </div>

            <div className="flex justify-center py-2">
              <TrustGauge score={report.credibility?.trust_score || 50} size={160} />
            </div>
            </motion.div>
          </InteractiveCard>

          {/* Component breakdowns */}
          {componentData.length > 0 && (
            <InteractiveCard className="border border-white/5 bg-[#071124]/30 backdrop-blur-xl">
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="p-5 space-y-4"
              >
              <h3 className="section-label">Signal Vectors</h3>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={componentData} layout="vertical" margin={{ left: -10, right: 10, top: 0, bottom: 0 }}>
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: 'rgba(255,255,255,0.2)', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }} axisLine={false} tickLine={false} width={80} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#071124', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', color: '#fff', fontSize: '11px' }}
                    formatter={(val) => [`${val.toFixed(0)}%`, 'Accuracy']}
                  />
                  <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={12}>
                    {componentData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.color} fillOpacity={0.7} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              </motion.div>
            </InteractiveCard>
          )}

          {/* Timeline Process Profile */}
          {report.credibility?.confidence_profile && (
            <InteractiveCard className="border border-white/5 bg-[#071124]/30 backdrop-blur-xl">
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25 }}
                className="p-5 space-y-4"
              >
              <h3 className="section-label">Risk Profile</h3>
              <div className="space-y-3.5">
                {Object.entries(report.credibility.confidence_profile).map(([key, value]) => (
                  <div key={key} className="space-y-1">
                    <div className="flex justify-between text-[11px] font-mono">
                      <span className="text-white/40 capitalize">{key.replace('_', ' ')}</span>
                      <span className="text-white/70">{typeof value === 'number' ? `${(value * 100).toFixed(0)}%` : value}</span>
                    </div>
                    {typeof value === 'number' && (
                      <div className="progress-bar">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${value * 100}%` }}
                          transition={{ duration: 1, delay: 0.3 }}
                          className="progress-fill bg-gradient-to-r from-sky-400 to-indigo-500"
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
              </motion.div>
            </InteractiveCard>
          )}

        </div>

        {/* Right Column: AI Research Details (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          
          {/* Explanation briefing */}
          {explanationText && (
            <InteractiveCard className="border border-white/10 bg-[#030712]/40 backdrop-blur-xl">
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 }}
                className="p-6 space-y-3"
              >
              <h3 className="section-label">Explainable Verdict</h3>
              <p className="text-white/85 text-xs sm:text-sm leading-relaxed font-sans">{explanationText}</p>
              </motion.div>
            </InteractiveCard>
          )}

          {/* Original Input Text / Meta */}
          {report.original_text && (
            <InteractiveCard className="border border-white/5 bg-[#071124]/30 backdrop-blur-xl">
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="p-6 space-y-4"
              >
              <h3 className="section-label">Ingested Material</h3>
              <div className="p-4 rounded-xl bg-white/[0.01] border border-white/5 max-h-40 overflow-y-auto">
                <p className="text-xs text-white/60 leading-relaxed italic">
                  "{report.original_text}"
                </p>
              </div>

              {/* Inconsistencies Found list */}
              {report.inconsistencies && report.inconsistencies.length > 0 && (
                <div className="space-y-3 pt-2">
                  <span className="text-[10px] font-bold text-red-400 uppercase tracking-widest flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                    Conflict Anomalies Found ({report.inconsistencies.length})
                  </span>
                  <div className="space-y-2">
                    {report.inconsistencies.map((inc, idx) => (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="flex items-start gap-2.5 p-2 rounded-lg bg-red-500/[0.02] border border-red-500/10 text-xs"
                      >
                        <span className={`px-2 py-0.5 rounded text-[8px] font-bold uppercase shrink-0 mt-0.5 ${
                          inc.severity === 'high' ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400'
                        }`}>
                          {inc.severity} Severity
                        </span>
                        <span className="text-white/60 leading-normal">{inc.reason}</span>
                      </motion.div>
                    ))}
                  </div>
                </div>
              )}
              </motion.div>
            </InteractiveCard>
          )}

          {/* Claim table listings */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="space-y-3"
          >
            <h3 className="section-label">Evidence Mapping</h3>
            <ClaimTable claims={report.claims} />
          </motion.div>

          {/* Counter Narrative section */}
          {report.counter_narrative && (
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <CounterNarrative narrative={report.counter_narrative} />
            </motion.div>
          )}

        </div>

      </div>

    </div>
  );
}
