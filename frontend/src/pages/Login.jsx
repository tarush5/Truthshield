import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Shield, Mail, KeyRound, Building2, ArrowRight, 
  Check, ChevronLeft, Plus, Loader2, AlertCircle, Sparkles, Github
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { supabase } from '../utils/supabase/client';
import InteractiveCard from '../components/InteractiveCard';


const STEPS = ['email', 'otp', 'workspace'];

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A10.96 10.96 0 001 12c0 1.77.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}

const slideVariants = {
  enter: (dir) => ({ x: dir > 0 ? 150 : -150, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (dir) => ({ x: dir > 0 ? -150 : 150, opacity: 0 }),
};

export default function Login() {
  const navigate = useNavigate();
  const { 
    signInWithOtp, verifyOtp, signInWithGoogle, 
    fetchOrganizations, createOrganization, setOrganization, 
    signUpWithPassword, signInWithPassword, signInAsDemo,
    isAuthenticated 
  } = useAuth();

  const [step, setStep] = useState('email');
  const [direction, setDirection] = useState(1);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authMethod, setAuthMethod] = useState('otp'); // 'otp' | 'password'
  const [passwordMode, setPasswordMode] = useState('signin'); // 'signin' | 'signup'
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

  // Handle password submit
  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password) return;
    setLoading(true);
    setError('');
    try {
      if (passwordMode === 'signin') {
        await signInWithPassword(email.trim(), password);
      } else {
        await signUpWithPassword(email.trim(), password);
      }
      goToStep('workspace');
    } catch (err) {
      setError(err.message || 'Authentication failed.');
    } finally {
      setLoading(false);
    }
  };

  // Handle Demo Mode login
  const handleDemoLogin = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await signInAsDemo();
      goToStep('workspace');
    } catch (err) {
      setError(err.message || 'Failed to initialize Demo Mode.');
    } finally {
      setLoading(false);
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

  // Handle GitHub login
  const handleGithubLogin = async () => {
    setLoading(true);
    setError('');
    try {
      // Supabase OAuth
      const { data, error: err } = await supabase.auth.signInWithOAuth({
        provider: 'github',
        options: {
          redirectTo: `${window.location.origin}/auth/callback`
        }
      });
      if (err) throw err;
    } catch (err) {
      setError(err.message || 'GitHub login failed.');
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
    <div className="min-h-[calc(100vh-6rem)] flex items-center justify-center px-4 py-12 relative z-10">
      
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        {/* Onboarding Frosted Card */}
        <InteractiveCard className="border border-white/10 shadow-2xl bg-[#030712]/40 backdrop-blur-xl">
          <div className="p-8 relative overflow-hidden">
            {/* Top glow */}
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-sky-400 via-purple-500 to-cyan-400" />


          {/* Title Header */}
          <div className="flex flex-col items-center justify-center mb-8">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sky-400 to-indigo-500 flex items-center justify-center mb-3 shadow-lg shadow-sky-500/20">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <h3 className="text-xl font-bold font-display text-white">TruthShield Access</h3>
            <p className="text-[10px] text-white/30 tracking-widest uppercase mt-0.5">Arctic Command Center</p>
          </div>

          {/* Stepper bar */}
          <div className="flex items-center justify-center gap-2 mb-8">
            {STEPS.map((s, i) => (
              <React.Fragment key={s}>
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-mono font-bold transition-all duration-300 ${
                  i <= stepIndex 
                    ? 'bg-sky-500/20 text-sky-400 border border-sky-400/40 shadow-[0_0_10px_rgba(14,165,233,0.15)]' 
                    : 'bg-white/5 text-white/20 border border-white/5'
                }`}>
                  {i < stepIndex ? <Check className="w-3.5 h-3.5" /> : i + 1}
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`w-8 h-[1px] transition-all duration-500 ${
                    i < stepIndex ? 'bg-sky-500/40' : 'bg-white/5'
                  }`} />
                )}
              </React.Fragment>
            ))}
          </div>

          {/* Action error alerts */}
          <AnimatePresence mode="wait">
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/25 mb-5"
              >
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                <span className="text-xs text-red-400">{error}</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Step forms slider */}
          <div className="relative overflow-hidden min-h-[260px]">
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
                  transition={{ duration: 0.35, ease: 'easeOut' }}
                  className="space-y-5"
                >
                  {/* Auth method tabs */}
                  <div className="flex bg-white/5 p-1 rounded-xl border border-white/5 mb-2">
                    <button
                      type="button"
                      onClick={() => { setAuthMethod('otp'); setError(''); }}
                      className={`flex-1 text-center py-2 text-xs font-medium rounded-lg transition-all ${
                        authMethod === 'otp'
                          ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                          : 'text-white/40 hover:text-white/70'
                      }`}
                    >
                      OTP Code
                    </button>
                    <button
                      type="button"
                      onClick={() => { setAuthMethod('password'); setError(''); }}
                      className={`flex-1 text-center py-2 text-xs font-medium rounded-lg transition-all ${
                        authMethod === 'password'
                          ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                          : 'text-white/40 hover:text-white/70'
                      }`}
                    >
                      Password Access
                    </button>
                  </div>

                  {authMethod === 'password' && (
                    <div className="flex justify-end gap-3 text-[10px] uppercase font-bold tracking-wider mb-1">
                      <button
                        type="button"
                        onClick={() => setPasswordMode('signin')}
                        className={passwordMode === 'signin' ? 'text-sky-400 font-bold' : 'text-white/30 hover:text-white/50'}
                      >
                        Sign In
                      </button>
                      <span className="text-white/10">|</span>
                      <button
                        type="button"
                        onClick={() => setPasswordMode('signup')}
                        className={passwordMode === 'signup' ? 'text-sky-400 font-bold' : 'text-white/30 hover:text-white/50'}
                      >
                        Register
                      </button>
                    </div>
                  )}

                  <div>
                    <label className="text-[10px] font-bold text-white/40 uppercase tracking-widest mb-1.5 block">
                      {authMethod === 'otp' ? 'Security Email' : 'Email Address'}
                    </label>
                    <div className="relative">
                      <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/20" />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="analyst@company.com"
                        className="input-field pl-10 text-sm"
                        required
                        autoFocus
                      />
                    </div>
                  </div>

                  {authMethod === 'password' && (
                    <div>
                      <label className="text-[10px] font-bold text-white/40 uppercase tracking-widest mb-1.5 block">Password</label>
                      <div className="relative">
                        <KeyRound className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/20" />
                        <input
                          type="password"
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          placeholder="••••••••"
                          className="input-field pl-10 text-sm"
                          required
                        />
                      </div>
                    </div>
                  )}

                  {authMethod === 'otp' ? (
                    <button
                      onClick={handleEmailSubmit}
                      disabled={loading || !email.trim()}
                      className="btn-primary w-full flex items-center justify-center gap-2 text-xs py-2.5"
                    >
                      {loading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          Verify Security Email
                          <ArrowRight className="w-4 h-4" />
                        </>
                      )}
                    </button>
                  ) : (
                    <button
                      onClick={handlePasswordSubmit}
                      disabled={loading || !email.trim() || !password}
                      className="btn-primary w-full flex items-center justify-center gap-2 text-xs py-2.5"
                    >
                      {loading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          {passwordMode === 'signin' ? 'Sign In to Workspace' : 'Create Security Account'}
                          <ArrowRight className="w-4 h-4" />
                        </>
                      )}
                    </button>
                  )}

                  <div className="relative my-4">
                    <div className="absolute inset-0 flex items-center">
                      <div className="w-full border-t border-white/5" />
                    </div>
                    <div className="relative flex justify-center text-[10px] uppercase tracking-wider">
                      <span className="px-2 bg-[#0c1223] text-white/20">or secure OAuth</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={handleGoogleLogin}
                      disabled={loading}
                      className="btn-secondary flex items-center justify-center gap-2 text-xs py-2"
                    >
                      <GoogleIcon />
                      <span>Google</span>
                    </button>
                    <button
                      onClick={handleGithubLogin}
                      disabled={loading}
                      className="btn-secondary flex items-center justify-center gap-2 text-xs py-2"
                    >
                      <Github className="w-4 h-4 text-white" />
                      <span>GitHub</span>
                    </button>
                  </div>

                  <div className="relative my-4">
                    <div className="absolute inset-0 flex items-center">
                      <div className="w-full border-t border-white/5" />
                    </div>
                    <div className="relative flex justify-center text-[10px] uppercase tracking-wider">
                      <span className="px-2 bg-[#0c1223] text-white/20">or guest sandbox</span>
                    </div>
                  </div>

                  <button
                    onClick={handleDemoLogin}
                    disabled={loading}
                    className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-dashed border-sky-500/30 bg-sky-500/5 hover:bg-sky-500/10 hover:border-sky-400/50 text-sky-400 text-xs font-bold transition-all shadow-[0_0_15px_rgba(14,165,233,0.05)] hover:shadow-[0_0_20px_rgba(14,165,233,0.15)] group"
                  >
                    <Sparkles className="w-4 h-4 animate-pulse group-hover:scale-110 transition-transform" />
                    <span>Initialize Demo Access (Guest Mode)</span>
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
                  transition={{ duration: 0.35, ease: 'easeOut' }}
                  className="space-y-6"
                >
                  <button onClick={() => goToStep('email')} className="flex items-center gap-1 text-[10px] text-white/30 hover:text-white/60 mb-2 transition-colors uppercase font-bold tracking-wider">
                    <ChevronLeft className="w-3.5 h-3.5" />
                    Reset Email
                  </button>

                  <div className="text-center space-y-1">
                    <h4 className="text-sm font-bold text-white">Enter Security Token</h4>
                    <p className="text-xs text-white/40">
                      Code dispatched to <span className="text-sky-300 font-medium font-mono">{email}</span>
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
                          className="w-10 h-12 text-center text-lg font-bold bg-white/5 border border-white/10 rounded-lg text-white
                                     focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 transition-all font-mono"
                          autoFocus={i === 0}
                        />
                      ))}
                    </div>

                    <button type="submit" disabled={loading || otp.join('').length !== 6} className="btn-primary w-full flex items-center justify-center gap-2 text-xs py-2.5">
                      {loading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          Authorize Session
                          <ArrowRight className="w-4 h-4" />
                        </>
                      )}
                    </button>
                  </form>

                  <p className="text-center text-[10px] text-white/20">
                    Token failed?{' '}
                    <button
                      onClick={() => { setOtp(['','','','','','']); handleEmailSubmit({ preventDefault: () => {} }); }}
                      className="text-sky-400 hover:underline"
                    >
                      Resend
                    </button>
                  </p>
                </motion.div>
              )}

              {/* ── Step 3: Workspace Selection ── */}
              {step === 'workspace' && (
                <motion.div
                  key="workspace"
                  custom={direction}
                  variants={slideVariants}
                  initial="enter"
                  animate="center"
                  exit="exit"
                  transition={{ duration: 0.35, ease: 'easeOut' }}
                  className="space-y-5"
                >
                  <div className="text-center space-y-1">
                    <h4 className="text-sm font-bold text-white">Select Workspace Node</h4>
                    <p className="text-xs text-white/40">Select a secure workspace to ingest threat feeds</p>
                  </div>

                  {/* Nodes list */}
                  <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                    {organizations.map((org) => (
                      <button
                        key={org.id}
                        onClick={() => handleSelectOrg(org)}
                        className="w-full flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/5 
                                   hover:bg-white/10 hover:border-white/15 transition-all text-left group"
                      >
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-500/20 to-indigo-500/20 border border-white/5 flex items-center justify-center text-xs font-bold text-sky-300">
                          {org.name.charAt(0).toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-bold text-white truncate">{org.name}</div>
                          <div className="text-[9px] text-white/30 uppercase mt-0.5 tracking-wider">{org.role || 'Member'}</div>
                        </div>
                        <ChevronLeft className="w-3.5 h-3.5 text-white/20 rotate-180 group-hover:text-white/50 transition-colors" />
                      </button>
                    ))}
                  </div>

                  {/* Create node */}
                  {!showNewOrg ? (
                    <button
                      onClick={() => setShowNewOrg(true)}
                      className="w-full flex items-center justify-center gap-2 p-3 rounded-xl border border-dashed border-white/10 
                                 text-white/30 hover:text-white/60 hover:border-white/20 hover:bg-white/5 transition-all text-xs"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Establish new workspace node
                    </button>
                  ) : (
                    <form onSubmit={handleCreateOrg} className="space-y-3">
                      <div className="relative">
                        <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                        <input
                          type="text"
                          value={newOrgName}
                          onChange={(e) => setNewOrgName(e.target.value)}
                          placeholder="Node name (e.g., EU Ops)"
                          className="input-field pl-9 text-xs"
                          autoFocus
                        />
                      </div>
                      <div className="flex gap-2">
                        <button type="button" onClick={() => setShowNewOrg(false)} className="btn-secondary flex-1 text-xs py-2">
                          Cancel
                        </button>
                        <button type="submit" disabled={loading || !newOrgName.trim()} className="btn-primary flex-1 text-xs py-2 flex items-center justify-center gap-1.5">
                          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Establish'}
                        </button>
                      </div>
                    </form>
                  )}

                  {organizations.length === 0 && !showNewOrg && (
                    <div className="text-center pt-2">
                      <button
                        onClick={() => {
                          setOrganization('personal', 'Personal Workspace');
                          navigate('/dashboard');
                        }}
                        className="text-[10px] text-white/30 hover:text-white/50 transition-colors font-bold uppercase tracking-wider"
                      >
                        Skip to Personal Node
                      </button>
                    </div>
                  )}
                </motion.div>
              )}

            </AnimatePresence>
          </div>
        </div>
      </InteractiveCard>
    </motion.div>
  </div>
);
}

