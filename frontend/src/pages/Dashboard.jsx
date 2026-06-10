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
      const res = await fetch(`${API_BASE}/stats`);
      if (res.ok) {
        setStats(await res.json());
      }
    } catch (err) {
      console.error('Stats fetch failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const verdictData = stats ? Object.entries(stats.verdicts || {})
    .filter(([, v]) => v > 0)
    .map(([key, value]) => ({ name: t(`verdicts.${key}`), value, color: VERDICT_COLORS[key] || '#64748b' })) : [];

  const langData = stats ? Object.entries(stats.language_distribution || {})
    .filter(([, v]) => v > 0)
    .map(([key, value]) => ({ name: t(`languages.${key}`), value, color: LANG_COLORS[key] || '#64748b' })) : [];

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
          <p className="text-white/40 text-sm mt-1">Real-time misinformation detection overview</p>
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
            icon: BarChart3, label: t('dashboard.total_analyses'),
            value: stats?.total_analyses || 0,
            color: '#3b93ff', bg: 'rgba(59,147,255,0.1)',
          },
          {
            icon: Shield, label: t('dashboard.avg_trust'),
            value: `${stats?.avg_trust_score?.toFixed(0) || 50}%`,
            color: trustColor(stats?.avg_trust_score || 50),
            bg: `${trustColor(stats?.avg_trust_score || 50)}15`,
          },
          {
            icon: AlertTriangle, label: 'False Claims',
            value: stats?.verdicts?.FALSE || 0,
            color: '#ef4444', bg: 'rgba(239,68,68,0.1)',
          },
          {
            icon: TrendingUp, label: 'Verified True',
            value: stats?.verdicts?.TRUE || 0,
            color: '#10b981', bg: 'rgba(16,185,129,0.1)',
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

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Verdict Distribution */}
        <div className="glass-card p-6 animate-in" style={{ animationDelay: '0.2s' }}>
          <h2 className="text-sm font-semibold text-white/40 uppercase tracking-wider mb-6">
            {t('dashboard.verdicts')}
          </h2>
          {verdictData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={verdictData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  dataKey="value"
                  stroke="none"
                  paddingAngle={4}
                >
                  {verdictData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} fillOpacity={0.8} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '12px',
                    color: '#fff',
                    fontSize: '13px',
                  }}
                />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  formatter={(value) => <span className="text-white/60 text-xs">{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[260px] text-white/20">
              No data yet. Analyze content to see statistics.
            </div>
          )}
        </div>

        {/* Language Distribution */}
        <div className="glass-card p-6 animate-in" style={{ animationDelay: '0.25s' }}>
          <h2 className="text-sm font-semibold text-white/40 uppercase tracking-wider mb-6">
            {t('dashboard.languages')}
          </h2>
          {langData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={langData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <XAxis dataKey="name" tick={{ fill: '#ffffff60', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#ffffff30', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '12px',
                    color: '#fff',
                  }}
                />
                <Bar dataKey="value" radius={[8, 8, 0, 0]} barSize={40}>
                  {langData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} fillOpacity={0.7} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[260px] text-white/20">
              No data yet. Analyze content to see statistics.
            </div>
          )}
        </div>
      </div>

      {/* Top Flagged Domains */}
      <div className="glass-card p-6 animate-in" style={{ animationDelay: '0.3s' }}>
        <h2 className="text-sm font-semibold text-white/40 uppercase tracking-wider mb-4">
          {t('dashboard.top_domains')}
        </h2>
        {stats?.top_flagged_domains && stats.top_flagged_domains.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {stats.top_flagged_domains.map((d, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-white/[0.03] border border-white/5">
                <span className="text-sm text-white/60 truncate">{d.domain}</span>
                <span className="badge-danger text-xs ml-2">{d.count} flags</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-white/20 text-sm text-center py-8">
            No flagged domains yet. Start analyzing content!
          </p>
        )}
      </div>
    </div>
  );
}
