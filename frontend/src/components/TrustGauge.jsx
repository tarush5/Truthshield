import React, { useMemo, useState, useEffect } from 'react';
import { motion } from 'framer-motion';

export default function TrustGauge({ score = 50, size = 200 }) {
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const [displayScore, setDisplayScore] = useState(0);

  const { color, bgColor, glowColor, label } = useMemo(() => {
    if (score >= 75) return { color: '#10b981', bgColor: 'rgba(16,185,129,0.1)', glowColor: 'rgba(16,185,129,0.3)', label: 'Likely Authentic' };
    if (score >= 55) return { color: '#f59e0b', bgColor: 'rgba(245,158,11,0.1)', glowColor: 'rgba(245,158,11,0.3)', label: 'Uncertain' };
    if (score >= 35) return { color: '#f97316', bgColor: 'rgba(249,115,22,0.1)', glowColor: 'rgba(249,115,22,0.3)', label: 'Likely Misleading' };
    return { color: '#ef4444', bgColor: 'rgba(239,68,68,0.1)', glowColor: 'rgba(239,68,68,0.3)', label: 'Likely False' };
  }, [score]);

  // Animated counter
  useEffect(() => {
    const duration = 1500;
    const start = performance.now();
    const animate = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayScore(Math.round(eased * score));
      if (progress < 1) requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
  }, [score]);

  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative" style={{ width: size, height: size }}>
        {/* Glow effect */}
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 0.3, scale: 1 }}
          transition={{ duration: 1, delay: 0.5 }}
          className="absolute inset-0 rounded-full blur-2xl"
          style={{ backgroundColor: color }}
        />

        <svg
          viewBox="0 0 100 100"
          className="w-full h-full -rotate-90"
          style={{ filter: `drop-shadow(0 0 10px ${glowColor})` }}
        >
          {/* Background circle */}
          <circle
            cx="50" cy="50" r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.05)"
            strokeWidth="8"
            strokeLinecap="round"
          />

          {/* Progress circle — animated with framer-motion */}
          <motion.circle
            cx="50" cy="50" r={radius}
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset }}
            transition={{ duration: 1.5, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
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
          <motion.span
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="text-5xl font-extrabold font-display tabular-nums"
            style={{ color }}
          >
            {displayScore}
          </motion.span>
          <span className="text-xs text-white/40 font-medium mt-0.5">/ 100</span>
        </div>
      </div>

      {/* Label */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.8 }}
        className="px-4 py-1.5 rounded-full text-sm font-semibold border"
        style={{
          color,
          backgroundColor: bgColor,
          borderColor: `${color}30`,
        }}
      >
        {label}
      </motion.div>
    </div>
  );
}
