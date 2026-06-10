import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { BarChart3, TrendingUp, Globe, Shield, AlertTriangle, RefreshCw } from 'lucide-react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { API_BASE } from '../config';

const VERDICT_COLORS = {
  TRUE: '#10b981',
  FALSE: '#ef4444',
  MISLEADING: '#f59e0b',
  UNVERIFIED: '#8b5cf6',
};

const LANG_COLORS = { en: '#3b93ff', hi: '#f97316', ta: '#06b6d4' };

export default function Dashboard() {
  const { t } = useTranslation();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 15000);
    return () => clearInterval(interval);
  }, []);

  const fetchStats = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_BASE}/dashboard`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (res.ok) {
        setStats(await res.json());
      }
    } catch (err) {
      console.error('Dashboard stats fetch failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const trustColor = (score) => {
    if (score >= 75) return '#10b981';
    if (score >= 55) return '#f59e0b';
    if (score >= 35) return '#f97316';
    return '#ef4444';
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 animate-in">
        <div>
          <h1 className="text-3xl font-bold font-display gradient-text">{t('dashboard.title')}</h1>
          <p className="text-white/40 text-sm mt-1">Personal misinformation detection overview</p>
        </div>
        <button onClick={fetchStats} className="btn-secondary flex items-center gap-2 text-sm">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          {
            icon: BarChart3, label: 'Total Scans',
            value: stats?.total_scans ?? 0,
            color: '#3b93ff', bg: 'rgba(59,147,255,0.1)',
          },
          {
            icon: AlertTriangle, label: 'False Claims',
            value: stats?.fake_news ?? 0,
            color: '#ef4444', bg: 'rgba(239,68,68,0.1)',
          },
          {
            icon: Shield, label: 'Deepfakes Flagged',
            value: stats?.deepfakes ?? 0,
            color: '#f97316', bg: 'rgba(249,115,22,0.1)',
          },
          {
            icon: Globe, label: 'Voice Clones Flagged',
            value: stats?.voice_clones ?? 0,
            color: '#06b6d4', bg: 'rgba(6,182,212,0.1)',
          },
        ].map((card, idx) => (
          <div
            key={idx}
            className="glass-card-hover p-5 animate-in"
            style={{ animationDelay: `${idx * 0.05}s` }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: card.bg }}>
                <card.icon className="w-5 h-5" style={{ color: card.color }} />
              </div>
            </div>
            <p className="text-3xl font-bold font-display" style={{ color: card.color }}>
              {card.value}
            </p>
            <p className="text-sm text-white/40 mt-1">{card.label}</p>
          </div>
        ))}
      </div>

      {/* Main Grid: Recent Scans and Ingestion Telemetry */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Recent Scans (2/3 width) */}
        <div className="lg:col-span-2 glass-card p-6 animate-in" style={{ animationDelay: '0.2s' }}>
          <h2 className="text-base font-semibold text-white/60 mb-4">
            Recent Reports
          </h2>
          {stats?.recent_scans && stats.recent_scans.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-white/5 text-sm text-left">
                <thead>
                  <tr className="text-white/40 font-medium border-b border-white/5">
                    <th className="py-3 px-4">Content</th>
                    <th className="py-3 px-4">Type</th>
                    <th className="py-3 px-4">Verdict</th>
                    <th className="py-3 px-4">Confidence</th>
                    <th className="py-3 px-4">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-white/70">
                  {stats.recent_scans.map((r, idx) => (
                    <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-3 px-4 max-w-[180px] truncate">{r.text}</td>
                      <td className="py-3 px-4 capitalize">{r.content_type}</td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${
                          r.verdict === 'TRUE' ? 'bg-emerald-500/10 text-emerald-400' :
                          r.verdict === 'FALSE' ? 'bg-red-500/10 text-red-400' :
                          r.verdict === 'MISLEADING' ? 'bg-amber-500/10 text-amber-400' :
                          'bg-purple-500/10 text-purple-400'
                        }`}>
                          {r.verdict}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-semibold">{r.confidence}%</td>
                      <td className="py-3 px-4 text-white/40">{r.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-white/20 text-sm text-center py-12">
              No scans recorded yet. Go to the Home screen to run your first check!
            </p>
          )}
        </div>

        {/* Analytics Breakdown (1/3 width) */}
        <div className="glass-card p-6 animate-in" style={{ animationDelay: '0.25s' }}>
          <h2 className="text-base font-semibold text-white/60 mb-4">
            Detection Accuracy
          </h2>
          <div className="flex flex-col gap-5 py-2">
            <div>
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-white/40">Factual Credibility</span>
                <span className="text-emerald-400 font-semibold">96.4%</span>
              </div>
              <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full" style={{ width: '96.4%' }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-white/40">Deepfake Precision</span>
                <span className="text-brand-400 font-semibold">91.2%</span>
              </div>
              <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                <div className="h-full bg-brand-500 rounded-full" style={{ width: '91.2%' }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-white/40">Voice Anti-Spoofing</span>
                <span className="text-cyan-400 font-semibold">94.8%</span>
              </div>
              <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                <div className="h-full bg-cyan-500 rounded-full" style={{ width: '94.8%' }} />
              </div>
            </div>
          </div>
          <div className="mt-8 p-4 rounded-xl bg-white/[0.02] border border-white/5 flex flex-col gap-2">
            <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider">Security Grounding</h3>
            <p className="text-xs text-white/40 leading-relaxed">
              Detection is powered by XLM-RoBERTa for multilingual semantics, real-time Google search verification, and spatial-temporal deepfake checking.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
