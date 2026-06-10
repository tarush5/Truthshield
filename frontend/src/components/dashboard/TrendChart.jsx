import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts';
import { TrendingUp } from 'lucide-react';

// Time range options
const RANGES = [
  { id: '7d',  label: '7d' },
  { id: '30d', label: '30d' },
  { id: '90d', label: '90d' },
];

/** Custom glass-card tooltip for the chart */
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-surface-800/95 backdrop-blur-xl border border-white/10 
                    rounded-xl px-4 py-3 shadow-2xl shadow-black/40">
      <p className="text-xs text-white/50 font-medium mb-1.5">{label}</p>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-white/60 capitalize">{entry.dataKey}:</span>
          <span className="font-semibold text-white">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * TrendChart — area chart showing scan & threat trends
 * @param {array}    data       - Array of { date, scans, threats }
 * @param {function} onRangeChange - Optional callback with range ID
 */
export default function TrendChart({ data, onRangeChange }) {
  const [activeRange, setActiveRange] = useState('7d');

  const handleRangeChange = (rangeId) => {
    setActiveRange(rangeId);
    if (onRangeChange) onRangeChange(rangeId);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.15, ease: [0.4, 0, 0.2, 1] }}
      className="glass-card p-6"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="section-title text-lg flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-brand-400" />
            Analysis Trend
          </h3>
          <p className="text-xs text-white/35 mt-1">Volume of scans and threats over time</p>
        </div>

        {/* Range toggle buttons */}
        <div className="flex items-center bg-white/[0.04] rounded-lg p-0.5 border border-white/[0.06]">
          {RANGES.map((range) => (
            <button
              key={range.id}
              onClick={() => handleRangeChange(range.id)}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all duration-200
                ${activeRange === range.id
                  ? 'bg-brand-500 text-white shadow-sm shadow-brand-500/30'
                  : 'text-white/40 hover:text-white/70'
                }`}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="h-64">
        {data && data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <defs>
                {/* Gradient for scans area */}
                <linearGradient id="gradientScans" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b93ff" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#3b93ff" stopOpacity={0} />
                </linearGradient>
                {/* Gradient for threats area */}
                <linearGradient id="gradientThreats" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ef4444" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.04)"
                vertical={false}
              />

              <XAxis
                dataKey="date"
                stroke="rgba(255,255,255,0.15)"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                dy={8}
              />
              <YAxis
                stroke="rgba(255,255,255,0.15)"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                dx={-4}
              />

              <Tooltip content={<CustomTooltip />} cursor={false} />

              <Area
                type="monotone"
                dataKey="scans"
                stroke="#3b93ff"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#gradientScans)"
                dot={false}
                activeDot={{
                  r: 4,
                  fill: '#3b93ff',
                  stroke: '#020617',
                  strokeWidth: 2,
                }}
              />
              <Area
                type="monotone"
                dataKey="threats"
                stroke="#ef4444"
                strokeWidth={1.5}
                fillOpacity={1}
                fill="url(#gradientThreats)"
                dot={false}
                activeDot={{
                  r: 3,
                  fill: '#ef4444',
                  stroke: '#020617',
                  strokeWidth: 2,
                }}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-white/20 text-sm">
            No trend data available
          </div>
        )}
      </div>
    </motion.div>
  );
}
