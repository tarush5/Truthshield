import React, { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight, Loader2, Mail, Shield } from 'lucide-react';

import { useAuth } from '../contexts/AuthContext';

/**
 * Sign in or create an account.
 *
 * Password and one-time-code sign-in share this screen. Nothing here reveals
 * whether an address is registered: the API returns the same response either
 * way, and the copy is written to match.
 */
export default function Login() {
  const navigate = useNavigate();
  const { isAuthenticated, signIn, signUp, requestOtp, verifyOtp } = useAuth();

  const [tab, setTab] = useState('password');   // password | code
  const [isNew, setIsNew] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [codeSent, setCodeSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (isAuthenticated) return <Navigate to="/analyze" replace />;

  const run = async (action) => {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const submitPassword = (e) => {
    e.preventDefault();
    run(async () => {
      await (isNew ? signUp(email, password) : signIn(email, password));
      navigate('/analyze');
    });
  };

  const submitCode = (e) => {
    e.preventDefault();
    run(async () => {
      if (!codeSent) {
        await requestOtp(email);
        setCodeSent(true);
        return;
      }
      await verifyOtp(email, code);
      navigate('/analyze');
    });
  };

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md items-center px-4">
      <div className="w-full space-y-6">
        <header className="space-y-2 text-center">
          <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl bg-brand/15">
            <Shield className="h-5 w-5 text-brand" />
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight text-ink">
            {isNew ? 'Create your account' : 'Welcome back'}
          </h1>
          <p className="text-sm text-ink-secondary">
            {isNew
              ? 'Your analyses are kept private to your account.'
              : 'Sign in to check claims and keep your history.'}
          </p>
        </header>

        <div className="card overflow-hidden">
          <div role="tablist" className="flex border-b border-line">
            {[
              { id: 'password', label: 'Password' },
              { id: 'code', label: 'Email code' },
            ].map(({ id, label }) => (
              <button
                key={id}
                role="tab"
                aria-selected={tab === id}
                onClick={() => { setTab(id); setError(''); }}
                className={`flex-1 px-4 py-3 text-sm font-semibold transition-colors ${
                  tab === id
                    ? 'bg-brand/10 text-brand'
                    : 'text-ink-muted hover:text-ink'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="space-y-4 p-5">
            {tab === 'password' ? (
              <form onSubmit={submitPassword} className="space-y-4">
                <Field
                  id="email" label="Email" type="email" value={email}
                  onChange={setEmail} autoComplete="email" disabled={busy}
                />
                <Field
                  id="password" label="Password" type="password" value={password}
                  onChange={setPassword} disabled={busy}
                  autoComplete={isNew ? 'new-password' : 'current-password'}
                  hint={isNew ? 'At least 10 characters, mixing letters with numbers or symbols.' : undefined}
                />
                <Submit busy={busy} disabled={!email || !password}>
                  {isNew ? 'Create account' : 'Sign in'}
                </Submit>
              </form>
            ) : (
              <form onSubmit={submitCode} className="space-y-4">
                <Field
                  id="otp-email" label="Email" type="email" value={email}
                  onChange={setEmail} autoComplete="email" disabled={busy || codeSent}
                />
                {codeSent && (
                  <Field
                    id="code" label="6-digit code" value={code} onChange={setCode}
                    inputMode="numeric" maxLength={6} disabled={busy}
                    hint="If that address has an account, a code is on its way."
                  />
                )}
                <Submit busy={busy} disabled={!email || (codeSent && code.length !== 6)}>
                  {codeSent ? 'Sign in' : 'Send me a code'}
                </Submit>
              </form>
            )}

            {error && (
              <p role="alert" className="flex items-start gap-2 text-sm text-status-critical-text">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                {error}
              </p>
            )}
          </div>
        </div>

        {tab === 'password' && (
          <p className="text-center text-sm text-ink-secondary">
            {isNew ? 'Already have an account?' : 'New here?'}{' '}
            <button
              onClick={() => { setIsNew(!isNew); setError(''); }}
              className="font-semibold text-brand hover:underline"
            >
              {isNew ? 'Sign in' : 'Create an account'}
            </button>
          </p>
        )}
      </div>
    </div>
  );
}

function Field({ id, label, hint, value, onChange, ...rest }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-ink">{label}</label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input-field"
        {...rest}
      />
      {hint && <p className="text-2xs text-ink-muted">{hint}</p>}
    </div>
  );
}

function Submit({ busy, disabled, children }) {
  return (
    <button type="submit" disabled={busy || disabled} className="btn-primary w-full">
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
      {children}
      {!busy && <ArrowRight className="h-4 w-4" />}
    </button>
  );
}
