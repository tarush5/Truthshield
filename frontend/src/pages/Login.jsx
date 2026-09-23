import React, { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import {
  ArrowRight, Check, Eye, EyeOff, KeyRound, Loader2, Lock, Mail, Shield,
} from 'lucide-react';

import { InlineError } from '../components/ui';
import { useAuth } from '../contexts/AuthContext';

/**
 * Sign in or create an account.
 *
 * Password and one-time-code sign-in share this screen. Nothing here reveals
 * whether an address is registered: the API returns the same response either
 * way, and the copy is written to match -- "if that address has an account"
 * rather than "we sent you a code".
 *
 * The panel beside the form is not decoration. A sign-in screen is where
 * someone decides whether to bother, so it answers "what do I get" at the
 * moment the question is actually being asked.
 */

const ASSURANCES = [
  'Your analyses stay private to your account',
  'Results are shareable only when you choose',
  'Every verdict lists the sources behind it',
];

export default function Login() {
  const navigate = useNavigate();
  const { isAuthenticated, signIn, signUp, requestOtp, verifyOtp } = useAuth();

  const [tab, setTab] = useState('password');   // password | code
  const [isNew, setIsNew] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [reveal, setReveal] = useState(false);
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
    <div className="mx-auto grid max-w-5xl items-center gap-12 px-5 py-12 sm:px-8 lg:grid-cols-[1fr_minmax(0,26rem)] lg:gap-16 lg:py-20">
      {/* ── Why bother ───────────────────────────────────────
          Hidden on a phone, where it would push the form below the fold and
          the reader already arrived intending to sign in. */}
      <div className="rise hidden lg:block">
        <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand/15">
          <Shield className="h-5 w-5 text-brand" aria-hidden="true" />
        </span>
        <h2 className="display mt-6 text-4xl">
          Check it before you <em>share</em> it.
        </h2>
        <p className="mt-4 max-w-prose text-base leading-relaxed text-ink-secondary text-pretty">
          Paste a claim and get a verdict with the sources behind it, plus an
          honest account of whatever could not be verified.
        </p>

        <ul className="mt-8 space-y-3">
          {ASSURANCES.map((line) => (
            <li key={line} className="flex items-start gap-2.5 text-[0.8125rem] text-ink-secondary">
              <Check
                className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[rgb(var(--c-good-text))]"
                aria-hidden="true"
              />
              {line}
            </li>
          ))}
        </ul>
      </div>

      {/* ── Form ─────────────────────────────────────────── */}
      <div className="rise rise-1 w-full">
        <header className="mb-6 text-center lg:text-left">
          <span className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-brand/15 lg:hidden">
            <Shield className="h-5 w-5 text-brand" aria-hidden="true" />
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-ink">
            {isNew ? 'Create your account' : 'Welcome back'}
          </h1>
          <p className="mt-1.5 text-sm text-ink-secondary">
            {isNew
              ? 'Your analyses are kept private to your account.'
              : 'Sign in to check claims and keep your history.'}
          </p>
        </header>

        <div className="card overflow-hidden">
          <div role="tablist" className="flex border-b border-line">
            {[
              { id: 'password', label: 'Password', icon: Lock },
              { id: 'code', label: 'Email code', icon: KeyRound },
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                role="tab"
                aria-selected={tab === id}
                tabIndex={tab === id ? 0 : -1}
                onClick={() => { setTab(id); setError(''); }}
                className="segment flex-1"
              >
                <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                {label}
              </button>
            ))}
          </div>

          <div className="space-y-4 p-5">
            {tab === 'password' ? (
              <form onSubmit={submitPassword} className="space-y-4" noValidate>
                <Field
                  id="email" label="Email" type="email" icon={Mail} value={email}
                  onChange={setEmail} autoComplete="email" disabled={busy}
                  placeholder="you@example.com"
                />
                <Field
                  id="password"
                  label="Password"
                  type={reveal ? 'text' : 'password'}
                  icon={Lock}
                  value={password}
                  onChange={setPassword}
                  disabled={busy}
                  autoComplete={isNew ? 'new-password' : 'current-password'}
                  hint={isNew ? 'At least 10 characters, mixing letters with numbers or symbols.' : undefined}
                  // A reveal toggle, because the alternative is retyping a
                  // long password from scratch after one mistyped character.
                  trailing={
                    <button
                      type="button"
                      onClick={() => setReveal((v) => !v)}
                      className="focusable rounded-md p-1 text-ink-muted transition-colors hover:text-ink"
                      aria-label={reveal ? 'Hide password' : 'Show password'}
                      aria-pressed={reveal}
                      tabIndex={-1}
                    >
                      {reveal ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </button>
                  }
                />
                <Submit busy={busy} disabled={!email || !password}>
                  {isNew ? 'Create account' : 'Sign in'}
                </Submit>
              </form>
            ) : (
              <form onSubmit={submitCode} className="space-y-4" noValidate>
                <Field
                  id="otp-email" label="Email" type="email" icon={Mail} value={email}
                  onChange={setEmail} autoComplete="email" disabled={busy || codeSent}
                  placeholder="you@example.com"
                />
                {codeSent && (
                  <Field
                    id="code" label="6-digit code" icon={KeyRound} value={code}
                    onChange={setCode} inputMode="numeric" maxLength={6} disabled={busy}
                    autoComplete="one-time-code"
                    className="!font-mono !tracking-[0.3em]"
                    hint="If that address has an account, a code is on its way."
                  />
                )}
                <Submit busy={busy} disabled={!email || (codeSent && code.length !== 6)}>
                  {codeSent ? 'Sign in' : 'Send me a code'}
                </Submit>
                {codeSent && (
                  <button
                    type="button"
                    onClick={() => { setCodeSent(false); setCode(''); setError(''); }}
                    className="w-full text-center text-[0.6875rem] text-ink-muted hover:text-ink focusable rounded"
                  >
                    Use a different address
                  </button>
                )}
              </form>
            )}

            {error && <InlineError>{error}</InlineError>}
          </div>
        </div>

        {tab === 'password' && (
          <p className="mt-5 text-center text-sm text-ink-secondary">
            {isNew ? 'Already have an account?' : 'New here?'}{' '}
            <button
              onClick={() => { setIsNew(!isNew); setError(''); }}
              className="focusable rounded font-semibold text-brand hover:underline"
            >
              {isNew ? 'Sign in' : 'Create an account'}
            </button>
          </p>
        )}
      </div>
    </div>
  );
}

function Field({ id, label, hint, icon: Icon, trailing, value, onChange, className = '', ...rest }) {
  const hintId = hint ? `${id}-hint` : undefined;

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-[0.8125rem] font-medium text-ink">
        {label}
      </label>
      <div className="relative">
        {Icon && (
          <Icon
            className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted"
            aria-hidden="true"
          />
        )}
        <input
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-describedby={hintId}
          className={`input-field ${Icon ? '!pl-10' : ''} ${trailing ? '!pr-10' : ''} ${className}`}
          {...rest}
        />
        {trailing && (
          <span className="absolute right-2.5 top-1/2 -translate-y-1/2">{trailing}</span>
        )}
      </div>
      {hint && <p id={hintId} className="text-[0.6875rem] text-ink-muted">{hint}</p>}
    </div>
  );
}

function Submit({ busy, disabled, children }) {
  return (
    <button type="submit" disabled={busy || disabled} className="btn-primary w-full">
      {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
      {children}
      {!busy && <ArrowRight className="h-4 w-4" aria-hidden="true" />}
    </button>
  );
}
