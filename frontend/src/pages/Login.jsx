import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Shield, Mail, KeyRound, Building2, ArrowRight, 
  Check, ChevronLeft, Plus, Loader2, AlertCircle, Sparkles
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const STEPS = ['email', 'otp', 'workspace'];

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A10.96 10.96 0 001 12c0 1.77.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}

const slideVariants = {
  enter: (dir) => ({ x: dir > 0 ? 200 : -200, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (dir) => ({ x: dir > 0 ? -200 : 200, opacity: 0 }),
};

export default function Login() {
  const navigate = useNavigate();
  const { 
    signInWithOtp, verifyOtp, signInWithGoogle, 
    fetchOrganizations, createOrganization, setOrganization, 
    isAuthenticated 
  } = useAuth();

  const [step, setStep] = useState('email');
  const [direction, setDirection] = useState(1);
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [organizations, setOrganizations] = useState([]);
  const [newOrgName, setNewOrgName] = useState('');
  const [showNewOrg, setShowNewOrg] = useState(false);

  // If already authenticated, check for organizations
  useEffect(() => {
    if (isAuthenticated && step === 'email') {
      goToStep('workspace');
    }
  }, [isAuthenticated]);

  const goToStep = (newStep) => {
    const currentIdx = STEPS.indexOf(step);
    const newIdx = STEPS.indexOf(newStep);
    setDirection(newIdx > currentIdx ? 1 : -1);
    setError('');
    setStep(newStep);
  };

  // Load organizations when reaching workspace step
  useEffect(() => {
    if (step === 'workspace') {
      loadOrganizations();
    }
  }, [step]);

  const loadOrganizations = async () => {
    try {
      const orgs = await fetchOrganizations();
      setOrganizations(orgs);
    } catch (e) {
      console.error('Failed to load organizations:', e);
    }
  };

  // Handle email submit
  const handleEmailSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    setError('');
    try {
      await signInWithOtp(email.trim());
      goToStep('otp');
    } catch (err) {
      setError(err.message || 'Failed to send OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Handle OTP input
  const handleOtpChange = (index, value) => {
    if (value.length > 1) value = value.slice(-1);
    if (!/^\d*$/.test(value)) return;
    
    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);

    // Auto-focus next input
    if (value && index < 5) {
      const next = document.getElementById(`otp-${index + 1}`);
      next?.focus();
    }
  };

  const handleOtpKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      const prev = document.getElementById(`otp-${index - 1}`);
      prev?.focus();
    }
  };

  // Handle OTP paste
  const handleOtpPaste = (e) => {
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (pasted.length > 0) {
      const newOtp = [...otp];
      pasted.split('').forEach((char, i) => { newOtp[i] = char; });
      setOtp(newOtp);
      const focusIdx = Math.min(pasted.length, 5);
      document.getElementById(`otp-${focusIdx}`)?.focus();
    }
  };

  // Verify OTP
  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    const code = otp.join('');
    if (code.length !== 6) return;
    setLoading(true);
    setError('');
    try {
      await verifyOtp(email, code);
      goToStep('workspace');
    } catch (err) {
      setError(err.message || 'Invalid code. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Handle Google login
  const handleGoogleLogin = async () => {
    setLoading(true);
    setError('');
    try {
      await signInWithGoogle();
    } catch (err) {
      setError(err.message || 'Google login failed.');
      setLoading(false);
    }
  };

  // Handle workspace selection
  const handleSelectOrg = (org) => {
    setOrganization(org.id, org.name);
    navigate('/dashboard');
  };

  // Handle create workspace
  const handleCreateOrg = async (e) => {
    e.preventDefault();
    if (!newOrgName.trim()) return;
    setLoading(true);
    setError('');
    try {
      const result = await createOrganization(newOrgName.trim());
      setOrganization(result.org_id || result.id, newOrgName.trim());
      navigate('/dashboard');
    } catch (err) {
      setError(err.message || 'Failed to create workspace.');
    } finally {
      setLoading(false);
    }
  };

  // Step progress indicator
  const stepIndex = STEPS.indexOf(step);

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center px-4 py-12 relative">
      {/* Background */}
      <div className="aurora-bg">
        <div className="aurora-blob aurora-blob-1" />
        <div className="aurora-blob aurora-blob-2" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative z-10 w-full max-w-md"
      >
        {/* Card */}
        <div className="glass-card p-8 relative overflow-hidden">
          {/* Top gradient accent */}
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-brand-500 via-cyan-500 to-brand-500" />

          {/* Logo */}
          <div className="flex items-center justify-center gap-2 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-brand-500/25">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold font-display gradient-text">TruthShield</span>
          </div>

          {/* Step indicator */}
          <div className="flex items-center justify-center gap-2 mb-8">
            {STEPS.map((s, i) => (
              <React.Fragment key={s}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 ${
                  i <= stepIndex 
                    ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/30' 
                    : 'bg-white/5 text-white/30 border border-white/10'
                }`}>
                  {i < stepIndex ? <Check className="w-4 h-4" /> : i + 1}
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`w-12 h-0.5 rounded transition-all duration-500 ${
                    i < stepIndex ? 'bg-brand-500' : 'bg-white/10'
                  }`} />
                )}
              </React.Fragment>
            ))}
          </div>

          {/* Error message */}
          <AnimatePresence mode="wait">
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 mb-4"
              >
                <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                <span className="text-sm text-red-400">{error}</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Step content */}
          <AnimatePresence mode="wait" custom={direction}>
            {/* ── Step 1: Email ── */}
            {step === 'email' && (
              <motion.div
                key="email"
                custom={direction}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.3 }}
              >
                <h2 className="text-xl font-bold font-display text-center mb-2">Welcome back</h2>
                <p className="text-sm text-white/40 text-center mb-6">Sign in to your TruthShield account</p>

                <form onSubmit={handleEmailSubmit} className="space-y-4">
                  <div>
                    <label className="text-xs font-semibold text-white/50 mb-1.5 block">Email address</label>
                    <div className="relative">
                      <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@example.com"
                        className="input-field pl-10"
                        required
                        autoFocus
                      />
                    </div>
                  </div>

                  <button type="submit" disabled={loading || !email.trim()} className="btn-primary w-full flex items-center justify-center gap-2">
                    {loading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>
                        Send Verification Code
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </form>

                <div className="relative my-6">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-white/10" />
                  </div>
                  <div className="relative flex justify-center text-xs">
                    <span className="px-3 bg-surface-900 text-white/30">or continue with</span>
                  </div>
                </div>

                <button
                  onClick={handleGoogleLogin}
                  disabled={loading}
                  className="btn-secondary w-full flex items-center justify-center gap-3"
                >
                  <GoogleIcon />
                  <span>Google</span>
                </button>
              </motion.div>
            )}

            {/* ── Step 2: OTP ── */}
            {step === 'otp' && (
              <motion.div
                key="otp"
                custom={direction}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.3 }}
              >
                <button onClick={() => goToStep('email')} className="flex items-center gap-1 text-xs text-white/40 hover:text-white/60 mb-4 transition-colors">
                  <ChevronLeft className="w-3 h-3" />
                  Back
                </button>

                <div className="text-center mb-6">
                  <div className="w-14 h-14 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center mx-auto mb-4">
                    <KeyRound className="w-6 h-6 text-brand-400" />
                  </div>
                  <h2 className="text-xl font-bold font-display mb-1">Check your email</h2>
                  <p className="text-sm text-white/40">
                    We sent a 6-digit code to<br/>
                    <span className="text-brand-400 font-medium">{email}</span>
                  </p>
                </div>

                <form onSubmit={handleVerifyOtp} className="space-y-6">
                  <div className="flex justify-center gap-2" onPaste={handleOtpPaste}>
                    {otp.map((digit, i) => (
                      <input
                        key={i}
                        id={`otp-${i}`}
                        type="text"
                        inputMode="numeric"
                        maxLength={1}
                        value={digit}
                        onChange={(e) => handleOtpChange(i, e.target.value)}
                        onKeyDown={(e) => handleOtpKeyDown(i, e)}
                        className="w-12 h-14 text-center text-xl font-bold bg-white/5 border border-white/10 rounded-xl text-white
                                   focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all"
                        autoFocus={i === 0}
                      />
                    ))}
                  </div>

                  <button type="submit" disabled={loading || otp.join('').length !== 6} className="btn-primary w-full flex items-center justify-center gap-2">
                    {loading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>
                        Verify & Continue
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </form>

                <p className="text-center mt-4 text-xs text-white/30">
                  Didn't receive it?{' '}
                  <button
                    onClick={() => { setOtp(['','','','','','']); handleEmailSubmit({ preventDefault: () => {} }); }}
                    className="text-brand-400 hover:underline"
                  >
                    Resend code
                  </button>
                </p>
              </motion.div>
            )}

            {/* ── Step 3: Workspace ── */}
            {step === 'workspace' && (
              <motion.div
                key="workspace"
                custom={direction}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.3 }}
              >
                <div className="text-center mb-6">
                  <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto mb-4">
                    <Building2 className="w-6 h-6 text-emerald-400" />
                  </div>
                  <h2 className="text-xl font-bold font-display mb-1">Choose your workspace</h2>
                  <p className="text-sm text-white/40">Select an existing workspace or create a new one</p>
                </div>

                {/* Existing workspaces */}
                <div className="space-y-2 mb-4 max-h-48 overflow-y-auto">
                  {organizations.map((org) => (
                    <button
                      key={org.id}
                      onClick={() => handleSelectOrg(org)}
                      className="w-full flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/5 
                                 hover:bg-white/10 hover:border-white/15 transition-all group text-left"
                    >
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500/30 to-cyan-500/30 flex items-center justify-center text-sm font-bold text-brand-300">
                        {org.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-semibold truncate">{org.name}</div>
                        <div className="text-xs text-white/30">{org.role || 'Member'}</div>
                      </div>
                      <ChevronLeft className="w-4 h-4 text-white/20 rotate-180 group-hover:text-white/50 transition-colors" />
                    </button>
                  ))}
                </div>

                {/* Create new workspace */}
                {!showNewOrg ? (
                  <button
                    onClick={() => setShowNewOrg(true)}
                    className="w-full flex items-center justify-center gap-2 p-3 rounded-xl border border-dashed border-white/10 
                               text-white/40 hover:text-white/60 hover:border-white/20 hover:bg-white/5 transition-all text-sm"
                  >
                    <Plus className="w-4 h-4" />
                    Create new workspace
                  </button>
                ) : (
                  <form onSubmit={handleCreateOrg} className="space-y-3">
                    <div className="relative">
                      <Building2 className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                      <input
                        type="text"
                        value={newOrgName}
                        onChange={(e) => setNewOrgName(e.target.value)}
                        placeholder="Workspace name"
                        className="input-field pl-10"
                        autoFocus
                      />
                    </div>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => setShowNewOrg(false)} className="btn-secondary flex-1 text-sm py-2.5">
                        Cancel
                      </button>
                      <button type="submit" disabled={loading || !newOrgName.trim()} className="btn-primary flex-1 text-sm py-2.5 flex items-center justify-center gap-2">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create'}
                      </button>
                    </div>
                  </form>
                )}

                {/* Skip for personal use */}
                {organizations.length === 0 && !showNewOrg && (
                  <div className="mt-4 text-center">
                    <button
                      onClick={() => {
                        setOrganization('personal', 'Personal');
                        navigate('/dashboard');
                      }}
                      className="text-xs text-white/30 hover:text-white/50 transition-colors"
                    >
                      Skip — use personal workspace
                    </button>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Bottom accent */}
          <div className="flex items-center justify-center gap-1.5 mt-8 text-xs text-white/20">
            <Sparkles className="w-3 h-3" />
            <span>Secured by TruthShield</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
