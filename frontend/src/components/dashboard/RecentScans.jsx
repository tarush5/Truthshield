import React from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { FileText, ExternalLink, Inbox } from 'lucide-react';
import InteractiveCard from '../InteractiveCard';

// Map verdict strings to badge classes
const VERDICT_BADGE = {
  TRUE:                    'badge-success',
  VERIFIED:                'badge-success',
  'LIKELY TRUE':           'badge-success opacity-85',
  'PARTIALLY TRUE':        'badge-warning',
  FALSE:                   'badge-danger',
  'LIKELY FALSE':          'badge-danger opacity-85',
  MISLEADING:              'badge-warning',
  'MIXED EVIDENCE':        'badge-warning',
  UNVERIFIED:              'badge-info',
  'INSUFFICIENT EVIDENCE': 'badge-info',
};

// Map content types to readable labels
const TYPE_LABELS = {
  text:  'Text',
  image: 'Image',
  audio: 'Audio',
  video: 'Video',
  url:   'URL',
};

/**
 * RecentScans — table of recent analysis results
 * @param {array}   scans     - Array of scan objects
 * @param {boolean} fullPage  - If true, render with page header
 */
export default function RecentScans({ scans, fullPage = false, loading = false }) {
  const navigate = useNavigate();

  if (loading || !scans) {
    return <RecentScansSkeleton fullPage={fullPage} />;
  }

  // Format date string to relative or absolute
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
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  // Truncate content text
  const truncate = (text, maxLen = 60) => {
    if (!text) return '—';
    return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
  };

  const isEmpty = scans.length === 0;

  return (
    <InteractiveCard className="border border-white/5 bg-[#030712]/40 backdrop-blur-xl overflow-hidden">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2, ease: [0.4, 0, 0.2, 1] }}
        className="p-6"
      >

      {/* Header */}
      <div className="flex items-center justify-between p-6 pb-0">
        <div>
          <h3 className={`font-semibold text-white/80 flex items-center gap-2
            ${fullPage ? 'section-title text-xl' : 'text-sm'}`}>
            <FileText className="w-4 h-4 text-brand-400" />
            Recent Scans
          </h3>
          <p className="text-xs text-white/35 mt-1">
            {isEmpty ? 'No activity yet' : `${scans.length} results`}
          </p>
        </div>
      </div>

      {/* Content */}
      {isEmpty ? (
        /* Empty state */
        <div className="flex flex-col items-center justify-center py-16 px-6">
          <div className="w-14 h-14 rounded-2xl bg-white/[0.04] flex items-center justify-center mb-4">
            <Inbox className="w-7 h-7 text-white/15" />
          </div>
          <p className="text-sm text-white/30 font-medium text-center">
            No scans yet
          </p>
          <p className="text-xs text-white/20 mt-1 text-center max-w-[240px]">
            Start analyzing content to see results appear here.
          </p>
        </div>
      ) : (
        /* Table */
        <div className="overflow-x-auto mt-4">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="border-b border-white/[0.06]">
                {['Content', 'Type', 'Verdict', 'Confidence', 'Date'].map((h) => (
                  <th
                    key={h}
                    className="px-6 py-3 text-[11px] font-semibold text-white/30 
                               uppercase tracking-wider"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {scans.map((scan, idx) => (
                <motion.tr
                  key={scan.id || idx}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: idx * 0.03 }}
                  onClick={() => navigate(`/report/${scan.id}`)}
                  className="hover:bg-white/[0.02] cursor-pointer transition-colors group"
                >
                  {/* Content */}
                  <td className="px-6 py-3.5 max-w-[280px]">
                    <span className="text-white/70 group-hover:text-white transition-colors truncate block">
                      {truncate(scan.input_text || scan.text)}
                    </span>
                  </td>

                  {/* Type */}
                  <td className="px-6 py-3.5">
                    <span className="text-white/50 capitalize text-xs font-medium">
                      {TYPE_LABELS[scan.content_type] || scan.content_type || '—'}
                    </span>
                  </td>

                  {/* Verdict */}
                  <td className="px-6 py-3.5">
                    <span className={VERDICT_BADGE[scan.verdict] || 'badge-info'}>
                      {scan.verdict || 'UNKNOWN'}
                    </span>
                  </td>

                  {/* Confidence */}
                  <td className="px-6 py-3.5">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{
                            width: `${scan.confidence || 0}%`,
                            backgroundColor:
                              (scan.confidence || 0) >= 80 ? '#10b981' :
                              (scan.confidence || 0) >= 50 ? '#f59e0b' : '#ef4444',
                          }}
                        />
                      </div>
                      <span className="text-xs font-semibold text-white/60">
                        {scan.confidence ?? 0}%
                      </span>
                    </div>
                  </td>

                  {/* Date */}
                  <td className="px-6 py-3.5">
                    <span className="text-xs text-white/35">
                      {formatDate(scan.created_at || scan.date)}
                    </span>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      </motion.div>
    </InteractiveCard>
  );
}



function RecentScansSkeleton({ fullPage }) {
  return (
    <div className="glass-card p-6 animate-pulse">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="h-6 w-32 rounded bg-white/[0.06] mb-2" />
          <div className="h-3.5 w-16 rounded bg-white/[0.04]" />
        </div>
      </div>
      <div className="space-y-3 mt-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex items-center justify-between py-3 border-b border-white/5">
            <div className="h-4 w-1/3 rounded bg-white/[0.06]" />
            <div className="h-4 w-12 rounded bg-white/[0.04]" />
            <div className="h-4.5 w-16 rounded-full bg-white/[0.06]" />
            <div className="h-4 w-20 rounded bg-white/[0.06]" />
            <div className="h-4 w-14 rounded bg-white/[0.04]" />
          </div>
        ))}
      </div>
    </div>
  );
}

