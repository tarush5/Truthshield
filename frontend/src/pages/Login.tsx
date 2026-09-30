import { ArrowLeft } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { Logo } from '@/components/landing/Logo';
import { Button, ErrorNotice, Input, Label } from '@/components/ui';
import { cn } from '@/lib/format';
import { authService } from '@/services';
import { useAuth } from '@/stores/auth';

export default function Login() {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const setSession = useAuth((s) => s.setSession);
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/app';

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const response = mode === 'signin' ? await authService.signin(email, password) : await authService.signup(email, password);
      setSession(response);
      navigate(from.startsWith('/app') ? from : '/app', { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-16">
      <div className="accent-gradient pointer-events-none absolute -top-48 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full opacity-20 blur-[120px]" aria-hidden />
      <Link to="/" className="absolute left-6 top-6 inline-flex items-center gap-2 text-sm text-muted hover:text-text-primary">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Back
      </Link>

      <div className="relative w-full max-w-md">
        <div className="mb-10 flex flex-col items-center text-center">
          <Logo />
          <h1 className="mt-6 font-display text-5xl italic text-text-primary">{mode === 'signin' ? 'Welcome back' : 'Create an account'}</h1>
          <p className="mt-3 text-sm text-muted">
            {mode === 'signin' ? 'Sign in to open your investigations.' : 'Investigations are private to your account.'}
          </p>
        </div>

        <div className="mb-6 grid grid-cols-2 rounded-full border border-stroke bg-surface p-1" role="tablist" aria-label="Account">
          {(['signin', 'signup'] as const).map((m) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              onClick={() => {
                setMode(m);
                setError(null);
              }}
              className={cn('rounded-full py-2 text-sm transition-colors', mode === m ? 'bg-text-primary font-medium text-bg' : 'text-muted hover:text-text-primary')}
            >
              {m === 'signin' ? 'Sign in' : 'Sign up'}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="space-y-5 rounded-3xl border border-stroke bg-surface/60 p-6 backdrop-blur-md">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="password" hint={mode === 'signup' ? '10+ characters, letters and numbers' : undefined}>Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              required
              minLength={mode === 'signup' ? 10 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error !== null && <ErrorNotice error={error} />}
          <Button type="submit" loading={busy} className="w-full" innerClassName="w-full justify-center">
            {mode === 'signin' ? 'Sign in' : 'Create account'}
          </Button>
        </form>
        <p className="mt-6 text-center text-xs text-muted">
          Sessions use short-lived access tokens with rotating refresh tokens. Repeated failed sign-ins lock the address temporarily.
        </p>
      </div>
    </div>
  );
}
