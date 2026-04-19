import React, { useMemo } from 'react';

export default function TrustGauge({ score = 50, size = 200 }) {
  const radius = 45;
  const circumference = 2 * Math.PI * radius;

  const { color, bgColor, label } = useMemo(() => {
    if (score >= 75) return { color: '#10b981', bgColor: 'rgba(16,185,129,0.1)', label: 'Likely Authentic' };
    if (score >= 55) return { color: '#f59e0b', bgColor: 'rgba(245,158,11,0.1)', label: 'Uncertain' };
    if (score >= 35) return { color: '#f97316', bgColor: 'rgba(249,115,22,0.1)', label: 'Likely Misleading' };
    return { color: '#ef4444', bgColor: 'rgba(239,68,68,0.1)', label: 'Likely False' };
  }, [score]);

  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative" style={{ width: size, height: size }}>
        {/* Glow effect */}
        <div
          className="absolute inset-0 rounded-full blur-2xl opacity-30"
          style={{ backgroundColor: color }}
        />

        <svg
          viewBox="0 0 100 100"
          className="w-full h-full -rotate-90"
          style={{ filter: `drop-shadow(0 0 10px ${color}40)` }}
        >
          {/* Background circle */}
          <circle
            cx="50" cy="50" r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.05)"
            strokeWidth="8"
            strokeLinecap="round"
          />

          {/* Progress circle */}
          <circle
            cx="50" cy="50" r={radius}
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className="transition-all duration-1500 ease-out"
            style={{
              animation: 'gauge 1.5s ease-out forwards',
            }}
          />

          {/* Inner glow circle */}
          <circle
            cx="50" cy="50" r={radius - 6}
            fill={bgColor}
            stroke="none"
          />
        </svg>

        {/* Score text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="text-5xl font-extrabold font-display tabular-nums"
            style={{ color }}
          >
            {score}
          </span>
          <span className="text-xs text-white/40 font-medium mt-0.5">/ 100</span>
        </div>
      </div>

      {/* Label */}
      <div
        className="px-4 py-1.5 rounded-full text-sm font-semibold border"
        style={{
          color,
          backgroundColor: bgColor,
          borderColor: `${color}30`,
        }}
      >
        {label}
      </div>
    </div>
  );
}
