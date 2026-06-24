import React from 'react';
import { motion } from 'framer-motion';
import { Activity, UserPlus, Key, LogIn, Clock } from 'lucide-react';
import InteractiveCard from '../InteractiveCard';

// Action type → color + icon mapping
const ACTION_CONFIG = {
  ANALYSIS:   { color: '#3b93ff', bgColor: 'rgba(59,147,255,0.15)',  icon: Activity },
  INVITE:     { color: '#06b6d4', bgColor: 'rgba(6,182,212,0.15)',   icon: UserPlus },
  API_KEY:    { color: '#f59e0b', bgColor: 'rgba(245,158,11,0.15)',  icon: Key },
  LOGIN:      { color: '#10b981', bgColor: 'rgba(16,185,129,0.15)',  icon: LogIn },
};

// Fallback config for unknown action types
const DEFAULT_CONFIG = {
  color: 'rgba(255,255,255,0.4)',
  bgColor: 'rgba(255,255,255,0.06)',
  icon: Activity,
};

/**
 * Format a date to relative time (e.g., '2 min ago')
 */
function relativeTime(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const date = new Date(dateStr);
  const diffSec = Math.floor((now - date) / 1000);

  if (diffSec < 60) return 'Just now';
  if (diffSec < 3600) {
    const mins = Math.floor(diffSec / 60);
    return `${mins} min${mins > 1 ? 's' : ''} ago`;
  }
  if (diffSec < 86400) {
    const hrs = Math.floor(diffSec / 3600);
    return `${hrs} hour${hrs > 1 ? 's' : ''} ago`;
  }
  const days = Math.floor(diffSec / 86400);
  if (days < 7) return `${days} day${days > 1 ? 's' : ''} ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Stagger animation variants
const containerVariants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.06 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, x: -12 },
  show: {
    opacity: 1, x: 0,
    transition: { duration: 0.35, ease: [0.4, 0, 0.2, 1] },
  },
};

/**
 * ActivityFeed — vertical timeline of audit log entries
 * @param {array} logs - Array of { id, action, user_email, details, created_at }
 */
export default function ActivityFeed({ logs, loading = false }) {
  if (loading || !logs) {
    return <ActivityFeedSkeleton />;
  }
  const isEmpty = logs.length === 0;

  return (
    <InteractiveCard className="border border-white/5 bg-[#030712]/40 backdrop-blur-xl h-full">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.25, ease: [0.4, 0, 0.2, 1] }}
        className="p-6"
      >

      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-sm font-semibold text-white/80 flex items-center gap-2">
            <Clock className="w-4 h-4 text-brand-400" />
            Activity Feed
          </h3>
          <p className="text-xs text-white/30 mt-0.5">Recent workspace events</p>
        </div>
      </div>

      {isEmpty ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Activity className="w-8 h-8 text-white/10 mb-2" />
          <p className="text-xs text-white/25">No activity yet</p>
        </div>
      ) : (
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="space-y-1 max-h-[400px] overflow-y-auto pr-1"
        >
          {logs.map((log, idx) => {
            // Determine action type (match prefix)
            const actionKey = Object.keys(ACTION_CONFIG).find(
              (k) => log.action?.toUpperCase().includes(k)
            );
            const config = ACTION_CONFIG[actionKey] || DEFAULT_CONFIG;
            const Icon = config.icon;

            return (
              <motion.div
                key={log.id || idx}
                variants={itemVariants}
                className="flex items-start gap-3 p-2.5 rounded-xl 
                           hover:bg-white/[0.02] transition-colors group"
              >
                {/* Timeline dot + line */}
                <div className="flex flex-col items-center pt-0.5">
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
                    style={{ backgroundColor: config.bgColor }}
                  >
                    <Icon className="w-3.5 h-3.5" style={{ color: config.color }} />
                  </div>
                  {idx < logs.length - 1 && (
                    <div className="w-px h-full min-h-[16px] bg-white/[0.06] mt-1" />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 pt-0.5">
                  <p className="text-xs font-semibold text-white/70 group-hover:text-white/90 transition-colors">
                    {log.action}
                  </p>
                  <p className="text-[11px] text-white/35 truncate mt-0.5">
                    {log.user_email}
                    {log.details && (
                      <>
                        {' — '}
                        {typeof log.details === 'object'
                          ? log.details.verdict || log.details.label || JSON.stringify(log.details)
                          : log.details}
                      </>
                    )}

                  </p>
                </div>

                {/* Time */}
                <span className="text-[10px] text-white/20 shrink-0 pt-1 font-medium">
                  {relativeTime(log.created_at)}
                </span>
              </motion.div>
            );
          })}
        </motion.div>
        )}
      </motion.div>
    </InteractiveCard>
  );
}



function ActivityFeedSkeleton() {
  return (
    <div className="glass-card p-6 animate-pulse h-full">
      <div className="flex items-center justify-between mb-5">
        <div>
          <div className="h-5 w-28 rounded bg-white/[0.06] mb-1" />
          <div className="h-3 w-36 rounded bg-white/[0.04]" />
        </div>
      </div>
      <div className="space-y-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="flex items-start gap-3 py-1">
            <div className="w-7 h-7 rounded-lg bg-white/[0.06] shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-3.5 w-1/2 rounded bg-white/[0.06]" />
              <div className="h-3 w-3/4 rounded bg-white/[0.04]" />
            </div>
            <div className="h-3 w-8 rounded bg-white/[0.04]" />
          </div>
        ))}
      </div>
    </div>
  );
}
