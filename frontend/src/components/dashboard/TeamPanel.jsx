import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Users, UserPlus, Mail, RefreshCw, Check, AlertCircle } from 'lucide-react';
import { API_BASE } from '../../config';

// Role → color mapping
const ROLE_STYLE = {
  Admin:  'bg-brand-500/10 text-brand-400 border-brand-500/20',
  Member: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  Viewer: 'bg-white/5 text-white/40 border-white/10',
};

/**
 * TeamPanel — member list + invite form
 * @param {string} orgId - Active organization ID
 * @param {string} token - Auth token
 */
export default function TeamPanel({ orgId, token }) {
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('Member');
  const [inviting, setInviting] = useState(false);
  const [toast, setToast] = useState(null); // { type: 'success'|'error', message }

  // Show toast for 4 seconds
  const showToast = (type, message) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchMembers = useCallback(async () => {
    if (!orgId || !token) { setLoading(false); return; }
    try {
      const res = await fetch(`${API_BASE}/organizations/${orgId}/members`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMembers(data.members || data || []);
      }
    } catch (err) {
      console.error('Failed to fetch members:', err);
    } finally {
      setLoading(false);
    }
  }, [orgId, token]);

  useEffect(() => { fetchMembers(); }, [fetchMembers]);

  // Handle invite submission
  const handleInvite = async (e) => {
    e.preventDefault();
    if (!inviteEmail || !orgId) return;
    setInviting(true);
    try {
      const res = await fetch(`${API_BASE}/organizations/${orgId}/invite`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
      });
      if (res.ok) {
        setInviteEmail('');
        showToast('success', `Invitation sent to ${inviteEmail}`);
        fetchMembers();
      } else {
        const d = await res.json().catch(() => ({}));
        showToast('error', d.detail || 'Failed to send invitation');
      }
    } catch (err) {
      showToast('error', 'Network error — please try again');
    } finally {
      setInviting(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
      className="space-y-6"
    >
      {/* Toast notification */}
      {toast && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-medium
            ${toast.type === 'success'
              ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
              : 'bg-red-500/10 border border-red-500/20 text-red-400'
            }`}
        >
          {toast.type === 'success'
            ? <Check className="w-4 h-4 shrink-0" />
            : <AlertCircle className="w-4 h-4 shrink-0" />
          }
          {toast.message}
        </motion.div>
      )}

      {/* Members list */}
      <div className="glass-card overflow-hidden">
        <div className="p-6 pb-0 flex items-center justify-between">
          <div>
            <h3 className="section-title text-lg flex items-center gap-2">
              <Users className="w-5 h-5 text-brand-400" />
              Team Members
            </h3>
            <p className="text-xs text-white/30 mt-1">
              {members.length} member{members.length !== 1 ? 's' : ''} in workspace
            </p>
          </div>
          <button
            onClick={fetchMembers}
            className="p-2 rounded-lg hover:bg-white/5 text-white/30 hover:text-white/60 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {loading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center gap-3 animate-pulse">
                <div className="w-9 h-9 rounded-xl bg-white/[0.06]" />
                <div className="flex-1">
                  <div className="h-3.5 w-40 rounded bg-white/[0.06] mb-1.5" />
                  <div className="h-3 w-20 rounded bg-white/[0.04]" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="divide-y divide-white/[0.04] mt-4">
            {members.map((member, idx) => (
              <motion.div
                key={member.id || idx}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: idx * 0.04 }}
                className="flex items-center gap-3 px-6 py-3.5 hover:bg-white/[0.02] transition-colors"
              >
                {/* Avatar circle */}
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500/20 to-cyan-500/20
                                border border-white/[0.08] flex items-center justify-center shrink-0">
                  <span className="text-xs font-bold text-white/60">
                    {member.email?.[0]?.toUpperCase() || '?'}
                  </span>
                </div>

                {/* Email + date */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white/80 font-medium truncate">{member.email}</p>
                  <p className="text-[11px] text-white/30 mt-0.5">
                    Joined {new Date(member.joined_at || member.created_at).toLocaleDateString(
                      'en-US', { month: 'short', day: 'numeric', year: 'numeric' }
                    )}
                  </p>
                </div>

                {/* Role badge */}
                <span className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border
                  ${ROLE_STYLE[member.role] || ROLE_STYLE.Viewer}`}>
                  {member.role}
                </span>
              </motion.div>
            ))}

            {members.length === 0 && (
              <div className="py-12 text-center">
                <Users className="w-8 h-8 text-white/10 mx-auto mb-2" />
                <p className="text-xs text-white/25">No team members found</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Invite Form */}
      <div className="glass-card p-6">
        <h4 className="text-sm font-semibold text-white/70 flex items-center gap-2 mb-4">
          <UserPlus className="w-4 h-4 text-brand-400" />
          Invite Team Member
        </h4>

        <form onSubmit={handleInvite} className="flex flex-col sm:flex-row gap-3">
          {/* Email input */}
          <div className="relative flex-1">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-white/25">
              <Mail className="w-4 h-4" />
            </div>
            <input
              type="email"
              required
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="colleague@company.com"
              className="input-field pl-10 text-sm"
            />
          </div>

          {/* Role dropdown */}
          <select
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value)}
            className="px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white text-sm
                       focus:outline-none focus:border-brand-500/50 transition-all appearance-none
                       cursor-pointer"
          >
            <option value="Admin">Admin</option>
            <option value="Member">Member</option>
            <option value="Viewer">Viewer</option>
          </select>

          {/* Submit */}
          <button
            type="submit"
            disabled={inviting || !inviteEmail}
            className="btn-primary flex items-center justify-center gap-2 text-sm whitespace-nowrap"
          >
            {inviting ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <UserPlus className="w-4 h-4" />
                Send Invite
              </>
            )}
          </button>
        </form>
      </div>
    </motion.div>
  );
}
