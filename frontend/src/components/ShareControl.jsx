import React, { useState } from 'react';
import { Check, Copy, Link2, Loader2, Lock } from 'lucide-react';

import { useToast } from './ui';
import { api } from '../lib/api';

/**
 * Turn a private report into a public link, and take it back.
 *
 * The state a reader needs is "is this public right now", so that is what
 * the control says at rest — not "Share", which describes a button rather
 * than a fact. Revocation is presented as plainly as sharing: it is the
 * half people need in a hurry, and hiding it behind a menu is how a link
 * stays live longer than its owner intended.
 */

function shareUrl(token) {
  return `${window.location.origin}/shared/${token}`;
}

export default function ShareControl({ reportId, className = '' }) {
  const toast = useToast();
  const [token, setToken] = useState(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(null);

  const mint = async () => {
    setBusy(true);
    setError(null);
    try {
      const { token: minted } = await api.share(reportId);
      setToken(minted);
      // Copy on mint. Someone who shares a report is about to paste it, and
      // making them press a second button to get the thing they asked for
      // is a step with no decision in it.
      try {
        await navigator.clipboard.writeText(shareUrl(minted));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        toast.success('Link copied — anyone with it can read this report');
      } catch {
        // Clipboard blocked. The URL is on screen to select, so say that
        // rather than leaving the reader wondering whether it worked.
        toast.info('Link created. Copying is blocked here — select it to copy.');
      }
    } catch (err) {
      setError(err.message || 'Could not create a link.');
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.unshare(reportId);
      setToken(null);
      toast.success('Link revoked — every copy of it has stopped working');
    } catch (err) {
      setError(err.message || 'Could not revoke the link.');
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl(token));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast.success('Link copied');
    } catch {
      setError('Copying is blocked here — select the link above instead.');
    }
  };

  if (!token) {
    return (
      <div className={className}>
        <button onClick={mint} disabled={busy} className="btn-secondary !px-3 !py-1.5 text-sm">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Link2 className="h-3.5 w-3.5" />}
          Get a shareable link
        </button>
        {error && <p className="mt-1.5 text-[0.6875rem] text-[rgb(var(--c-critical-text))]">{error}</p>}
      </div>
    );
  }

  return (
    <div className={`rounded-xl border border-line p-3.5 ${className}`}>
      <div className="mb-2 flex items-center gap-2">
        <Link2 className="h-3.5 w-3.5 text-[rgb(var(--c-warning-text))]" />
        <span className="text-[0.8125rem] font-medium text-ink">
          Anyone with this link can read this report
        </span>
      </div>

      <div className="flex items-center gap-2">
        <input
          readOnly
          value={shareUrl(token)}
          onFocus={(e) => e.target.select()}
          className="input-field !py-1.5 flex-1 font-mono !text-[0.6875rem]"
          aria-label="Shareable link"
        />
        <button onClick={copy} className="btn-secondary !px-2.5 !py-1.5" aria-label="Copy link">
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>

      <div className="mt-2.5 flex items-center justify-between gap-3">
        <p className="text-[0.6875rem] leading-relaxed text-ink-muted">
          The link does not say who ran the check. Revoking stops every copy
          of it at once.
        </p>
        <button
          onClick={revoke}
          disabled={busy}
          className="btn-ghost shrink-0 !px-2 !py-1 !text-[0.6875rem]"
        >
          {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Lock className="h-3 w-3" />}
          Make private
        </button>
      </div>

      {error && <p className="mt-1.5 text-[0.6875rem] text-[rgb(var(--c-critical-text))]">{error}</p>}
    </div>
  );
}
