import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { 
  User, Lock, Bell, Settings, Globe, ShieldAlert, 
  Check, Save, Loader2, RefreshCw
} from 'lucide-react';

export default function SettingsPanel() {
  const [activeTab, setActiveTab] = useState('profile');
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  // Profile fields
  const [profile, setProfile] = useState({
    name: 'Analyst Alpha',
    email: localStorage.getItem('user') ? JSON.parse(localStorage.getItem('user'))?.email : 'analyst@truthshield.ai',
    role: 'Senior Security Auditor',
  });

  // Settings configs
  const [notifications, setNotifications] = useState({
    emailAlerts: true,
    weeklyDigest: false,
    severityHighOnly: true,
    webhookTrigger: false
  });

  const [preferences, setPreferences] = useState({
    theme: 'dark',
    language: 'en',
    refreshRate: '5s',
  });

  const handleSave = (e) => {
    e.preventDefault();
    setSaving(true);
    setSuccess(false);
    setTimeout(() => {
      setSaving(false);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    }, 1200);
  };

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'security', label: 'Security', icon: Lock },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'preferences', label: 'Preferences', icon: Settings },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
      className="grid grid-cols-1 lg:grid-cols-12 gap-8"
    >
      {/* Left sidebar nav tabs (3 cols) */}
      <div className="lg:col-span-3 space-y-2">
        <h3 className="section-label px-3 mb-4">Account Node</h3>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-xs font-semibold uppercase tracking-wider transition-all border ${
                isActive
                  ? 'bg-sky-500/10 text-sky-400 border-sky-400/30 shadow-[0_0_15px_rgba(14,165,233,0.05)]'
                  : 'text-white/45 hover:text-white/70 bg-transparent border-transparent hover:bg-white/[0.02]'
              }`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Right panel settings forms (9 cols) */}
      <div className="lg:col-span-9">
        <div className="glass-card p-6 md:p-8 border border-white/10 relative overflow-hidden">
          {/* Accent radial glow */}
          <div className="absolute -top-16 -right-16 w-48 h-48 bg-sky-500/5 rounded-full blur-3xl pointer-events-none" />

          <form onSubmit={handleSave} className="space-y-6">
            
            {/* ── PROFILE TAB ── */}
            {activeTab === 'profile' && (
              <div className="space-y-5">
                <div>
                  <h3 className="text-base font-bold text-white">Identity Details</h3>
                  <p className="text-xs text-white/30 mt-0.5">Your personal credentials in the workspace node.</p>
                </div>

                <div className="grid md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Display Name</label>
                    <input
                      type="text"
                      value={profile.name}
                      onChange={e => setProfile({...profile, name: e.target.value})}
                      className="input-field text-xs"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Auditing Role</label>
                    <input
                      type="text"
                      value={profile.role}
                      onChange={e => setProfile({...profile, role: e.target.value})}
                      className="input-field text-xs"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Authorized Email</label>
                  <input
                    type="email"
                    value={profile.email}
                    disabled
                    className="input-field text-xs opacity-50 cursor-not-allowed"
                  />
                </div>
              </div>
            )}

            {/* ── SECURITY TAB ── */}
            {activeTab === 'security' && (
              <div className="space-y-5">
                <div>
                  <h3 className="text-base font-bold text-white">Security Architecture</h3>
                  <p className="text-xs text-white/30 mt-0.5">Session protocols and key encryption indices.</p>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between p-4 bg-white/[0.01] border border-white/5 rounded-xl">
                    <div className="space-y-0.5">
                      <p className="text-xs font-bold text-white">Multi-Factor Authentication</p>
                      <p className="text-[10px] text-white/40">Secure verification logins using mobile OTP generators.</p>
                    </div>
                    <span className="badge-success">ACTIVE</span>
                  </div>

                  <div className="flex items-center justify-between p-4 bg-white/[0.01] border border-white/5 rounded-xl">
                    <div className="space-y-0.5">
                      <p className="text-xs font-bold text-white">Session Expiration</p>
                      <p className="text-[10px] text-white/40">Force re-authorization after 24 hours of inactivity.</p>
                    </div>
                    <span className="badge-info">24 HOURS</span>
                  </div>
                </div>

                <div className="pt-2 border-t border-white/5">
                  <button type="button" className="btn-secondary text-xs py-2 px-4 flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-sky-400" />
                    Revoke All Active Sessions
                  </button>
                </div>
              </div>
            )}

            {/* ── NOTIFICATIONS TAB ── */}
            {activeTab === 'notifications' && (
              <div className="space-y-5">
                <div>
                  <h3 className="text-base font-bold text-white">Alert Dispatch Settings</h3>
                  <p className="text-xs text-white/30 mt-0.5">Configure when and how automated alerts are generated.</p>
                </div>

                <div className="space-y-4">
                  {[
                    { key: 'emailAlerts', label: 'Ingestion Alerts', desc: 'Dispatched on fact-check complete results.' },
                    { key: 'weeklyDigest', label: 'Weekly Trend digest', desc: 'Weekly summary charts mapping threat surges.' },
                    { key: 'severityHighOnly', label: 'High Severity Only', desc: 'Mute alerts unless confidence threshold exceeds 80% false.' },
                  ].map((item) => (
                    <div key={item.key} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                      <div>
                        <p className="text-xs font-bold text-white">{item.label}</p>
                        <p className="text-[10px] text-white/40 mt-0.5">{item.desc}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setNotifications({ ...notifications, [item.key]: !notifications[item.key] })}
                        className={`w-10 h-5 rounded-full p-0.5 transition-colors relative shrink-0 ${
                          notifications[item.key] ? 'bg-sky-500' : 'bg-white/10'
                        }`}
                      >
                        <div className={`w-4 h-4 bg-white rounded-full transition-transform ${
                          notifications[item.key] ? 'translate-x-5' : 'translate-x-0'
                        }`} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── PREFERENCES TAB ── */}
            {activeTab === 'preferences' && (
              <div className="space-y-5">
                <div>
                  <h3 className="text-base font-bold text-white">Workspace Node Preferences</h3>
                  <p className="text-xs text-white/30 mt-0.5">Local layout, language selection, and reload frequencies.</p>
                </div>

                <div className="grid md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Interface Language</label>
                    <select
                      value={preferences.language}
                      onChange={e => setPreferences({...preferences, language: e.target.value})}
                      className="px-4 py-3 bg-[#071124]/45 border border-white/10 rounded-xl text-white text-xs w-full focus:outline-none focus:border-[#7dd3fc]/50 cursor-pointer"
                    >
                      <option value="en">English (US)</option>
                      <option value="hi">Hindi (हिन्दी)</option>
                      <option value="ta">Tamil (தமிழ்)</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Inference Refresh Velocity</label>
                    <select
                      value={preferences.refreshRate}
                      onChange={e => setPreferences({...preferences, refreshRate: e.target.value})}
                      className="px-4 py-3 bg-[#071124]/45 border border-white/10 rounded-xl text-white text-xs w-full focus:outline-none focus:border-[#7dd3fc]/50 cursor-pointer"
                    >
                      <option value="1s">High Velocity (1s)</option>
                      <option value="5s">Standard (5s)</option>
                      <option value="30s">Lazy (30s)</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* Submit & Status Bar */}
            <div className="flex items-center justify-between pt-6 border-t border-white/5">
              <div className="min-h-[24px]">
                <AnimatePresence>
                  {success && (
                    <motion.div
                      initial={{ opacity: 0, x: -5 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -5 }}
                      className="flex items-center gap-1.5 text-xs text-emerald-400 font-bold"
                    >
                      <Check className="w-4 h-4" />
                      Changes verified & saved
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              <button
                type="submit"
                disabled={saving}
                className="btn-primary flex items-center gap-2 text-xs py-2 px-5"
              >
                {saving ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <>
                    <Save className="w-3.5 h-3.5" />
                    Save Settings
                  </>
                )}
              </button>
            </div>

          </form>
        </div>
      </div>
    </motion.div>
  );
}
