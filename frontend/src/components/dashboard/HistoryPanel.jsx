import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  Search, Clock, Filter, ChevronRight, Inbox,
  ShieldCheck, ShieldAlert, ShieldQuestion, FileText
} from 'lucide-react';
import InteractiveCard from '../InteractiveCard';

// Verdict filter chips
const FILTER_CHIPS = [
  { id: 'all',        label: 'All',         icon: null,            color: 'white' },
  { id: 'verified',   label: 'Verified',    icon: ShieldCheck,     color: 'emerald' },
  { id: 'misleading', label: 'Misleading',  icon: ShieldAlert,     color: 'amber' },
  { id: 'false',      label: 'False',       icon: ShieldAlert,     color: 'red' },
  { id: 'unverified', label: 'Unverified',  icon: ShieldQuestion,  color: 'blue' },
];

// Map verdict string to filter category
const verdictToFilter = (verdict) => {
  if (!verdict) return 'unverified';
  const v = verdict.toUpperCase();
  if (v.includes('TRUE') || v.includes('AUTHENTIC') || v.includes('VERIFIED')) return 'verified';
  if (v.includes('FALSE')) return 'false';
  if (v.includes('MISLEADING') || v.includes('MIXED')) return 'misleading';
  return 'unverified';
};

// Verdict badge classes
const VERDICT_STYLES = {
  verified:   { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20' },
  misleading: { bg: 'bg-amber-500/10',   text: 'text-amber-400',   border: 'border-amber-500/20' },
  false:      { bg: 'bg-red-500/10',     text: 'text-red-400',     border: 'border-red-500/20' },
  unverified: { bg: 'bg-blue-500/10',    text: 'text-blue-400',    border: 'border-blue-500/20' },
};

// Content type labels
const TYPE_LABELS = {
  text:  'Text',
  image: 'Image',
  audio: 'Audio',
  video: 'Video',
  url:   'URL',
};

const ITEMS_PER_PAGE = 10;

/**
 * HistoryPanel — Full analysis history with search and filters
 */
export default function HistoryPanel({ scans = [], loading = false }) {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);

  // Format relative date
  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  // Truncate text
  const truncate = (text, maxLen = 80) => {
    if (!text) return 'Untitled analysis';
    return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
  };

  // Filter and search
  const filteredScans = useMemo(() => {
    let result = [...scans];

    // Apply verdict filter
    if (activeFilter !== 'all') {
      result = result.filter(s => verdictToFilter(s.verdict) === activeFilter);
    }

    // Apply search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(s => {
        const text = (s.input_text || s.text || '').toLowerCase();
        const verdict = (s.verdict || '').toLowerCase();
        return text.includes(q) || verdict.includes(q);
      });
    }

    return result;
  }, [scans, activeFilter, searchQuery]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filteredScans.length / ITEMS_PER_PAGE));
  const paginatedScans = filteredScans.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  // Reset page when filter/search changes
  React.useEffect(() => {
    setCurrentPage(1);
  }, [activeFilter, searchQuery]);

  // Count per category
  const counts = useMemo(() => {
    const c = { all: scans.length, verified: 0, misleading: 0, false: 0, unverified: 0 };
    scans.forEach(s => { c[verdictToFilter(s.verdict)]++; });
    return c;
  }, [scans]);

  if (loading) return <HistorySkeleton />;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2.5">
            <Clock className="w-5 h-5 text-brand-400" />
            Analysis History
          </h2>
          <p className="text-sm text-white/35 mt-1">
            {scans.length} total {scans.length === 1 ? 'analysis' : 'analyses'}
          </p>
        </div>
      </div>

      {/* Search & Filters */}
      <InteractiveCard className="border border-white/5 bg-[#030712]/40 backdrop-blur-xl">
        <div className="p-4 space-y-3">
          {/* Search bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/25" />
            <input
              type="text"
              placeholder="Search analyses..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08]
                         text-sm text-white placeholder-white/25 
                         focus:outline-none focus:border-brand-500/40 focus:bg-white/[0.06]
                         transition-all duration-200"
            />
          </div>

          {/* Filter chips */}
          <div className="flex items-center gap-2 flex-wrap">
            <Filter className="w-3.5 h-3.5 text-white/20 shrink-0" />
            {FILTER_CHIPS.map((chip) => {
              const isActive = activeFilter === chip.id;
              return (
                <button
                  key={chip.id}
                  onClick={() => setActiveFilter(chip.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                              transition-all duration-200 border
                    ${isActive
                      ? 'bg-brand-500/10 text-brand-400 border-brand-500/20'
                      : 'bg-white/[0.02] text-white/40 border-white/[0.06] hover:text-white/60 hover:bg-white/[0.04]'
                    }`}
                >
                  {chip.icon && <chip.icon className="w-3 h-3" />}
                  {chip.label}
                  <span className={`text-[10px] ml-0.5 ${isActive ? 'text-brand-300' : 'text-white/25'}`}>
                    {counts[chip.id]}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </InteractiveCard>

      {/* Results */}
      <InteractiveCard className="border border-white/5 bg-[#030712]/40 backdrop-blur-xl overflow-hidden">
        <AnimatePresence mode="wait">
          {paginatedScans.length === 0 ? (
            /* Empty state */
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center py-16 px-6"
            >
              <div className="w-14 h-14 rounded-2xl bg-white/[0.04] flex items-center justify-center mb-4">
                <Inbox className="w-7 h-7 text-white/15" />
              </div>
              <p className="text-sm text-white/30 font-medium text-center">
                {searchQuery || activeFilter !== 'all' ? 'No matching analyses found' : 'No analyses yet'}
              </p>
              <p className="text-xs text-white/20 mt-1 text-center max-w-[240px]">
                {searchQuery || activeFilter !== 'all'
                  ? 'Try adjusting your search or filters.'
                  : 'Start analyzing content to build your history.'}
              </p>
            </motion.div>
          ) : (
            <motion.div
              key="results"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="divide-y divide-white/[0.04]"
            >
              {paginatedScans.map((scan, idx) => {
                const category = verdictToFilter(scan.verdict);
                const style = VERDICT_STYLES[category];
                const confidence = scan.confidence ?? 0;

                return (
                  <motion.button
                    key={scan.id || idx}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.03 }}
                    onClick={() => navigate(`/report/${scan.id}`)}
                    className="w-full flex items-center gap-4 px-5 py-4 
                               hover:bg-white/[0.02] transition-all group text-left"
                  >
                    {/* Icon */}
                    <div className={`w-10 h-10 rounded-xl ${style.bg} flex items-center justify-center 
                                    shrink-0 border ${style.border}`}>
                      <FileText className={`w-4 h-4 ${style.text}`} />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white/70 group-hover:text-white transition-colors truncate">
                        {truncate(scan.input_text || scan.text)}
                      </p>
                      <div className="flex items-center gap-3 mt-1">
                        {/* Type */}
                        <span className="text-[10px] text-white/30 font-medium uppercase tracking-wider">
                          {TYPE_LABELS[scan.content_type] || scan.content_type || 'Text'}
                        </span>
                        <span className="text-white/10">·</span>
                        {/* Date */}
                        <span className="text-[10px] text-white/25">
                          {formatDate(scan.created_at || scan.date)}
                        </span>
                      </div>
                    </div>

                    {/* Verdict badge */}
                    <div className="flex items-center gap-3 shrink-0">
                      <span className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold 
                                        ${style.bg} ${style.text} border ${style.border}`}>
                        {scan.verdict || 'PENDING'}
                      </span>

                      {/* Confidence mini-bar */}
                      <div className="hidden sm:flex items-center gap-1.5 w-16">
                        <div className="flex-1 h-1 rounded-full bg-white/[0.06] overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{
                              width: `${confidence}%`,
                              backgroundColor:
                                confidence >= 80 ? '#10b981' :
                                confidence >= 50 ? '#f59e0b' : '#ef4444',
                            }}
                          />
                        </div>
                        <span className="text-[10px] font-semibold text-white/40 w-7 text-right">
                          {confidence}%
                        </span>
                      </div>

                      <ChevronRight className="w-4 h-4 text-white/15 group-hover:text-white/40 
                                                transition-colors shrink-0" />
                    </div>
                  </motion.button>
                );
              })}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-white/[0.04]">
            <span className="text-xs text-white/25">
              Page {currentPage} of {totalPages}
            </span>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border border-white/[0.06]
                           text-white/40 hover:text-white hover:bg-white/[0.04] transition-all
                           disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border border-white/[0.06]
                           text-white/40 hover:text-white hover:bg-white/[0.04] transition-all
                           disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </InteractiveCard>
    </div>
  );
}


function HistorySkeleton() {
  return (
    <div className="space-y-5">
      <div className="animate-pulse">
        <div className="h-7 w-48 rounded bg-white/[0.06] mb-2" />
        <div className="h-4 w-24 rounded bg-white/[0.04]" />
      </div>
      <div className="glass-card p-4 animate-pulse space-y-3">
        <div className="h-10 w-full rounded-xl bg-white/[0.04]" />
        <div className="flex gap-2">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-7 w-20 rounded-lg bg-white/[0.04]" />
          ))}
        </div>
      </div>
      <div className="glass-card animate-pulse">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="flex items-center gap-4 px-5 py-4 border-b border-white/[0.04]">
            <div className="w-10 h-10 rounded-xl bg-white/[0.04]" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-3/4 rounded bg-white/[0.06]" />
              <div className="h-3 w-1/3 rounded bg-white/[0.04]" />
            </div>
            <div className="h-6 w-20 rounded-lg bg-white/[0.04]" />
          </div>
        ))}
      </div>
    </div>
  );
}
