import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { BarChart3, AlertTriangle, Eye, ShieldCheck, TrendingUp, TrendingDown } from 'lucide-react';

/**
 * AnimatedCounter — smoothly counts from 0 to `target` over `duration` ms
 */
function AnimatedCounter({ target, duration = 1500 }) {
  const [count, setCount] = useState(0);
  const startTime = useRef(null);
  const rafId = useRef(null);

  useEffect(() => {
    if (!target || target <= 0) { setCount(0); return; }

    // Ease-out cubic for natural deceleration
    const easeOut = (t) => 1 - Math.pow(1 - t, 3);

    const animate = (timestamp) => {
      if (!startTime.current) startTime.current = timestamp;
      const elapsed = timestamp - startTime.current;
      const progress = Math.min(elapsed / duration, 1);
      const easedProgress = easeOut(progress);

      setCount(Math.round(easedProgress * target));

      if (progress < 1) {
        rafId.current = requestAnimationFrame(animate);
      }
    };

    startTime.current = null;
    rafId.current = requestAnimationFrame(animate);

    return () => {
      if (rafId.current) cancelAnimationFrame(rafId.current);
    };
  }, [target, duration]);

  return <>{count.toLocaleString()}</>;
}

// Stat card definitions
const STAT_CARDS = [
  {
    key: 'total_analyses',
    label: 'Total Scans',
    icon: BarChart3,
    color: '#3b93ff',       // brand-500
    bgColor: 'rgba(59,147,255,0.08)',
    borderColor: 'rgba(59,147,255,0.3)',
    change: '+12.5%',
    isPositive: true,
  },
  {
    key: 'fake_news_detected',
    label: 'Threats Found',
    icon: AlertTriangle,
    color: '#ef4444',       // red-500
    bgColor: 'rgba(239,68,68,0.08)',
    borderColor: 'rgba(239,68,68,0.3)',
    change: '+3.2%',
    isPositive: false,  // more threats = negative
  },
  {
    key: 'deepfakes_detected',
    label: 'Deepfakes',
    icon: Eye,
    color: '#f59e0b',       // amber-500
    bgColor: 'rgba(245,158,11,0.08)',
    borderColor: 'rgba(245,158,11,0.3)',
    change: '+1.8%',
    isPositive: false,
  },
  {
    key: 'voice_clones_detected',
    label: 'Trust Score',
    icon: ShieldCheck,
    color: '#10b981',       // emerald-500
    bgColor: 'rgba(16,185,129,0.08)',
    borderColor: 'rgba(16,185,129,0.3)',
    change: '+4.1%',
    isPositive: true,
  },
];

// Container stagger animation
const containerVariants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.08 },
  },
};

const cardVariants = {
  hidden: { opacity: 0, y: 20, scale: 0.97 },
  show: {
    opacity: 1, y: 0, scale: 1,
    transition: { duration: 0.4, ease: [0.4, 0, 0.2, 1] },
  },
};

/**
 * StatsGrid — 4-column KPI cards with animated counters
 * @param {object} stats - { total_analyses, fake_news_detected, deepfakes_detected, voice_clones_detected }
 */
export default function StatsGrid({ stats }) {
  if (!stats) return <StatsGridSkeleton />;

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4"
    >
      {STAT_CARDS.map((card) => {
        const Icon = card.icon;
        const value = stats[card.key] ?? 0;

        return (
          <motion.div
            key={card.key}
            variants={cardVariants}
            className="glass-card-hover relative overflow-hidden group"
            style={{ borderLeftWidth: '3px', borderLeftColor: card.borderColor }}
          >
            <div className="p-5">
              {/* Header row */}
              <div className="flex items-center justify-between mb-4">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ backgroundColor: card.bgColor }}
                >
                  <Icon className="w-5 h-5" style={{ color: card.color }} />
                </div>

                {/* Change indicator */}
                <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold
                  ${card.isPositive
                    ? 'bg-emerald-500/10 text-emerald-400'
                    : 'bg-red-500/10 text-red-400'
                  }`}
                >
                  {card.isPositive
                    ? <TrendingUp className="w-3 h-3" />
                    : <TrendingDown className="w-3 h-3" />
                  }
                  {card.change}
                </div>
              </div>

              {/* Value */}
              <p className="text-3xl font-bold font-display tracking-tight" style={{ color: card.color }}>
                <AnimatedCounter target={value} />
              </p>

              {/* Label */}
              <p className="text-sm text-white/40 mt-1 font-medium">{card.label}</p>
            </div>

            {/* Subtle gradient glow on hover */}
            <div
              className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
              style={{
                background: `radial-gradient(ellipse at 20% 50%, ${card.bgColor}, transparent 70%)`,
              }}
            />
          </motion.div>
        );
      })}
    </motion.div>
  );
}

/** Skeleton placeholder while loading */
function StatsGridSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="glass-card p-5 animate-pulse">
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded-xl bg-white/[0.06]" />
            <div className="w-16 h-5 rounded-full bg-white/[0.06]" />
          </div>
          <div className="h-8 w-20 rounded-lg bg-white/[0.06] mb-2" />
          <div className="h-4 w-24 rounded bg-white/[0.04]" />
        </div>
      ))}
    </div>
  );
}
