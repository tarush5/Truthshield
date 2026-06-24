import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Key, Plus, Copy, Check, Trash2, RefreshCw, AlertTriangle, Shield, Eye, EyeOff
} from 'lucide-react';
import { API_BASE } from '../../config';

/**
 * APIKeysPanel — create, view, and revoke API keys
 * @param {string} orgId - Active organization ID
 * @param {string} token - Auth token
 */
export default function APIKeysPanel({ orgId, token }) {
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newLabel, setNewLabel] = useState('');
  const [generating, setGenerating] = useState(false);
  const [generatedKey, setGeneratedKey] = useState('');
  const [copied, setCopied] = useState(false);
  const [revokeConfirm, setRevokeConfirm] = useState(null); // key ID being confirmed
  const [revoking, setRevoking] = useState(false);

  const fetchKeys = useCallback(async () => {
    if (!orgId || !token) { setLoading(false); return; }
    try {
      const res = await fetch(`${API_BASE}/organizations/${orgId}/apikeys`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setKeys(data.keys || data || []);
      }
    } catch (err) {
      console.error('Failed to fetch API keys:', err);
    } finally {
      setLoading(false);
    }
  }, [orgId, token]);

  useEffect(() => { fetchKeys(); }, [fetchKeys]);

  // Create new key
  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newLabel || !orgId) return;
    setGenerating(true);
    setGeneratedKey('');
    try {
      const res = await fetch(`${API_BASE}/organizations/${orgId}/apikeys`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ label: newLabel }),
      });
      if (res.ok) {
        const data = await res.json();
        setGeneratedKey(data.raw_key || data.api_key || '');
        setNewLabel('');
        fetchKeys();
      }
    } catch (err) {
      console.error('Key creation failed:', err);
    } finally {
      setGenerating(false);
    }
  };

  // Copy key to clipboard
  const copyKey = () => {
    navigator.clipboard.writeText(generatedKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  // Revoke key (with inline confirmation)
  const handleRevoke = async (keyId) => {
    setRevoking(true);
    try {
      const res = await fetch(`${API_BASE}/apikeys/${keyId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setRevokeConfirm(null);
        fetchKeys();
      }
    } catch (err) {
      console.error('Revoke failed:', err);
    } finally {
      setRevoking(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
      className="space-y-6"
    >
      {/* ── Create Key Section ── */}
      <div className="glass-card p-6">
        <h3 className="section-title text-lg flex items-center gap-2 mb-1">
          <Key className="w-5 h-5 text-brand-400" />
          API Keys
        </h3>
        <p className="text-xs text-white/30 mb-6">
          Generate keys to authenticate with the TruthShield REST API.
        </p>

        <form onSubmit={handleCreate} className="flex flex-col sm:flex-row gap-3 max-w-xl">
          <input
            type="text"
            required
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            placeholder="Key label (e.g., CI/CD Pipeline)"
            className="input-field text-sm flex-1"
          />
          <button
            type="submit"
            disabled={generating || !newLabel}
            className="btn-primary flex items-center justify-center gap-2 text-sm whitespace-nowrap"
          >
            {generating ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <Plus className="w-4 h-4" />
                Generate Key
              </>
            )}
          </button>
        </form>

        {/* One-time key display */}
        <AnimatePresence>
          {generatedKey && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3 }}
              className="mt-6 overflow-hidden"
            >
              <div className="p-4 rounded-xl bg-emerald-500/[0.08] border border-emerald-500/20">
                <div className="flex items-center justify-between mb-2">
                  <span className="flex items-center gap-1.5 text-xs font-bold text-emerald-400 uppercase tracking-wider">
                    <Check className="w-3.5 h-3.5" />
                    Key Generated Successfully
                  </span>
                  <button
                    onClick={copyKey}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg 
                               bg-emerald-500/10 hover:bg-emerald-500/20 
                               text-emerald-400 text-xs font-semibold transition-colors"
                  >
                    {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    {copied ? 'Copied!' : 'Copy'}
                  </button>
                </div>

                <p className="text-[11px] text-white/40 mb-3 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3 text-amber-400" />
                  This key will only be shown once. Store it securely.
                </p>

                <div className="p-3 rounded-lg bg-surface-900/80 font-mono text-xs 
                                text-emerald-300 break-all select-all border border-emerald-500/10">
                  {generatedKey}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Active Keys Table ── */}
      <div className="glass-card overflow-hidden">
        <div className="p-6 pb-0">
          <h3 className="text-sm font-semibold text-white/70 flex items-center gap-2">
            <Shield className="w-4 h-4 text-brand-400" />
            Active Keys
          </h3>
        </div>

        {loading ? (
          <div className="p-6 space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="flex items-center gap-4 animate-pulse">
                <div className="h-4 w-32 rounded bg-white/[0.06]" />
                <div className="h-4 w-40 rounded bg-white/[0.04]" />
                <div className="h-4 w-20 rounded bg-white/[0.04]" />
              </div>
            ))}
          </div>
        ) : keys.length > 0 ? (
          <div className="overflow-x-auto mt-4">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {['Label', 'Key Prefix', 'Created', 'Status', 'Actions'].map((h) => (
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
                {keys.map((key) => (
                  <tr key={key.id} className="hover:bg-white/[0.02] transition-colors">
                    {/* Label */}
                    <td className="px-6 py-3.5 font-semibold text-white/90">{key.label}</td>

                    {/* Key prefix */}
                    <td className="px-6 py-3.5">
                      <code className="text-xs font-mono text-white/40 bg-white/[0.04] 
                                       px-2 py-1 rounded-md">
                        {key.key_prefix || 'ts_live_'}••••••••
                      </code>
                    </td>

                    {/* Created date */}
                    <td className="px-6 py-3.5 text-white/40 text-xs">
                      {new Date(key.created_at).toLocaleDateString('en-US', {
                        month: 'short', day: 'numeric', year: 'numeric'
                      })}
                    </td>

                    {/* Status */}
                    <td className="px-6 py-3.5">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full 
                                        text-[10px] font-bold
                        ${key.is_active !== false
                          ? 'bg-emerald-500/10 text-emerald-400'
                          : 'bg-red-500/10 text-red-400'
                        }`}>
                        <span className={`w-1.5 h-1.5 rounded-full 
                          ${key.is_active !== false ? 'bg-emerald-400' : 'bg-red-400'}`} />
                        {key.is_active !== false ? 'Active' : 'Revoked'}
                      </span>
                    </td>

                    {/* Actions */}
                    <td className="px-6 py-3.5">
                      {revokeConfirm === key.id ? (
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] text-red-400 font-medium">Revoke?</span>
                          <button
                            onClick={() => handleRevoke(key.id)}
                            disabled={revoking}
                            className="px-2 py-1 rounded-md bg-red-500/15 text-red-400 
                                       text-[11px] font-bold hover:bg-red-500/25 transition-colors"
                          >
                            {revoking ? '...' : 'Yes'}
                          </button>
                          <button
                            onClick={() => setRevokeConfirm(null)}
                            className="px-2 py-1 rounded-md bg-white/5 text-white/40 
                                       text-[11px] font-medium hover:bg-white/10 transition-colors"
                          >
                            No
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setRevokeConfirm(key.id)}
                          className="p-2 rounded-lg hover:bg-red-500/10 text-white/25 
                                     hover:text-red-400 transition-colors"
                          title="Revoke key"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-14 px-6">
            <Key className="w-8 h-8 text-white/10 mb-2" />
            <p className="text-sm text-white/25 font-medium">No API keys yet</p>
            <p className="text-xs text-white/15 mt-1 text-center max-w-[260px]">
              Generate your first key above to start using the TruthShield API.
            </p>
          </div>
        )}
      </div>
    </motion.div>
  );
}
