import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE } from '../config';

// Dashboard sub-components
import DashboardLayout from '../components/dashboard/DashboardLayout';
import StatsGrid from '../components/dashboard/StatsGrid';
import TrendChart from '../components/dashboard/TrendChart';
import RecentScans from '../components/dashboard/RecentScans';
import ActivityFeed from '../components/dashboard/ActivityFeed';
import HistoryPanel from '../components/dashboard/HistoryPanel';
import SettingsPanel from '../components/dashboard/SettingsPanel';

// Page transition variants
const pageVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.4, 0, 0.2, 1] } },
  exit:    { opacity: 0, y: -8, transition: { duration: 0.2 } },
};

/**
 * Dashboard — main authenticated dashboard page
 * Renders different sub-views based on sidebar navigation:
 *   - overview: Stats, charts, recent activity
 *   - history: Full past analyses with search/filter
 *   - settings: User preferences (via profile menu)
 */
export default function Dashboard() {
  const navigate = useNavigate();
  const [activeView, setActiveView] = useState('overview');

  // Auth & org context
  const token = localStorage.getItem('token');
  const orgId = localStorage.getItem('active_org_id');

  // Data state
  const [dashData, setDashData] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch main dashboard data
  const fetchDashboard = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const url = orgId
        ? `${API_BASE}/dashboard?org_id=${orgId}`
        : `${API_BASE}/dashboard`;
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error('Failed to load dashboard');
      setDashData(await res.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, orgId]);

  // Fetch audit logs for activity feed
  const fetchLogs = useCallback(async () => {
    if (!orgId || !token) return;
    try {
      const res = await fetch(`${API_BASE}/organizations/${orgId}/audit-logs`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setAuditLogs(data.logs || data || []);
      }
    } catch (err) {
      console.error('Logs fetch error:', err);
    }
  }, [orgId, token]);

  // Load data based on active view
  useEffect(() => {
    fetchDashboard();
    if (activeView === 'overview') fetchLogs();
  }, [activeView, fetchDashboard, fetchLogs]);

  // Handle view changes — redirect 'analyze' to /analyze page
  const handleViewChange = (view) => {
    if (view === 'analyze') {
      navigate('/analyze');
      return;
    }
    setActiveView(view);
  };

  return (
    <DashboardLayout activeView={activeView} onViewChange={handleViewChange}>
      <AnimatePresence mode="wait">
        {/* ── Overview ── */}
        {activeView === 'overview' && (
          <motion.div key="overview" {...pageVariants} className="space-y-6">
            <StatsGrid stats={dashData} loading={loading} />
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              <div className="xl:col-span-2">
                <TrendChart data={dashData?.weekly_trend} loading={loading} />
              </div>
              <div className="xl:col-span-1">
                <ActivityFeed logs={auditLogs} loading={loading} />
              </div>
            </div>
            <RecentScans scans={dashData?.recent_scans} loading={loading} />
          </motion.div>
        )}

        {/* ── History ── */}
        {activeView === 'history' && (
          <motion.div key="history" {...pageVariants}>
            <HistoryPanel scans={dashData?.recent_scans || []} loading={loading} />
          </motion.div>
        )}

        {/* ── Settings (via profile menu) ── */}
        {activeView === 'settings' && (
          <motion.div key="settings" {...pageVariants}>
            <SettingsPanel />
          </motion.div>
        )}
      </AnimatePresence>
    </DashboardLayout>
  );
}
