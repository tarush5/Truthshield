import React, { useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle, ArrowRight, FileText, Link2, Loader2, Upload, X,
} from 'lucide-react';

import { ApiError, api, pollReport } from '../lib/api';

/**
 * The submission surface.
 *
 * One decision shapes this page: the analysis takes seconds, so the wait has
 * to be honest. The previous version ran a timer that advanced fake pipeline
 * stages on a fixed interval regardless of what the server was doing — it
 * showed "Verifying" while the request was still queued, and reached the last
 * stage before any result existed. Progress here is either real (polled from
 * the server for queued jobs) or simply a spinner.
 */

const MODES = [
  { id: 'text', label: 'Text', icon: FileText },
  { id: 'url', label: 'Link', icon: Link2 },
  { id: 'file', label: 'File', icon: Upload },
];

const MAX_FILE_MB = 25;

export default function Analyze() {
  const navigate = useNavigate();

  const [mode, setMode] = useState('text');
  const [text, setText] = useState('');
  const [url, setUrl] = useState('');
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);

  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState(null);

  const fileInput = useRef(null);
  const abort = useRef(null);

  const ready =
    (mode === 'text' && text.trim().length >= 15) ||
    (mode === 'url' && url.trim().length > 4) ||
    (mode === 'file' && file);

  const pickFile = useCallback((chosen) => {
    if (!chosen) return;
    if (chosen.size > MAX_FILE_MB * 1024 * 1024) {
      setError(new Error(`That file is larger than the ${MAX_FILE_MB} MB limit.`));
      return;
    }
    setError(null);
    setFile(chosen);
  }, []);

  const submit = async () => {
    if (!ready || busy) return;

    setBusy(true);
    setError(null);
    setStatus('Reading your submission');
    abort.current = new AbortController();

    try {
      const result = await api.analyze({
        text: mode === 'text' ? text.trim() : undefined,
        url: mode === 'url' ? url.trim() : undefined,
        file: mode === 'file' ? file : undefined,
        signal: abort.current.signal,
      });

      // Large media is queued to a worker; poll until it settles rather than
      // holding the request open.
      if (result.status === 'queued') {
        setStatus('Queued — this one runs in the background');
        await pollReport(result.id, {
          signal: abort.current.signal,
          onTick: (r) => setStatus(
            r.status === 'running' ? 'Analyzing' : 'Waiting for a free worker',
          ),
        });
      }

      navigate(`/report/${result.id}`);
    } catch (err) {
      if (err.name === 'AbortError') return;
      setError(err);
      setBusy(false);
      setStatus('');
    }
  };

  const cancel = () => {
    abort.current?.abort();
    setBusy(false);
    setStatus('');
  };

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-4 sm:px-6 lg:px-8">
      <header className="space-y-3 text-center">
        <p className="eyebrow justify-center">Check a claim</p>
        <h1 className="text-3xl font-extrabold tracking-tight text-ink sm:text-4xl">
          Is this true?
        </h1>
        <p className="mx-auto max-w-lg text-pretty text-sm text-ink-secondary">
          Paste a claim, link an article, or upload a file. You will get a verdict,
          the sources behind it, and an explicit list of anything that could not
          be checked.
        </p>
      </header>

      <div className="card overflow-hidden">
        {/* Mode selector */}
        <div
          role="tablist"
          aria-label="What are you checking?"
          className="flex border-b border-line"
        >
          {MODES.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              role="tab"
              aria-selected={mode === id}
              disabled={busy}
              onClick={() => { setMode(id); setError(null); }}
              className={`flex flex-1 items-center justify-center gap-2 px-4 py-3 text-sm font-semibold transition-colors disabled:opacity-50 ${
                mode === id
                  ? 'bg-brand-500/10 text-brand-400'
                  : 'text-ink-muted hover:bg-white/[0.03] hover:text-ink'
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>

        <div className="p-5">
          {mode === 'text' && (
            <div className="space-y-2">
              <label htmlFor="claim" className="sr-only">Claim to check</label>
              <textarea
                id="claim"
                rows={6}
                value={text}
                disabled={busy}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste the claim, post, or article text here…"
                className="input-field resize-y"
              />
              <div className="flex items-center justify-between text-2xs text-ink-muted">
                <span>
                  {text.trim().length < 15 && text.length > 0
                    ? 'A little more text gives a better result'
                    : 'Tip: one specific claim works better than a whole article'}
                </span>
                <span className="tabular-nums">{text.length.toLocaleString()}</span>
              </div>
            </div>
          )}

          {mode === 'url' && (
            <div className="space-y-2">
              <label htmlFor="url" className="sr-only">Article link</label>
              <input
                id="url"
                type="url"
                value={url}
                disabled={busy}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/article"
                className="input-field"
              />
              <p className="text-2xs text-ink-muted">
                We fetch the page and check the claims in it. Links to private or
                internal addresses are refused.
              </p>
            </div>
          )}

          {mode === 'file' && (
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                pickFile(e.dataTransfer.files?.[0]);
              }}
              onClick={() => !busy && fileInput.current?.click()}
              className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition-colors ${
                dragging
                  ? 'border-brand-400 bg-brand-500/10'
                  : 'border-line hover:border-line-strong hover:bg-white/[0.02]'
              } ${busy ? 'pointer-events-none opacity-50' : ''}`}
            >
              <input
                ref={fileInput}
                type="file"
                className="hidden"
                disabled={busy}
                accept="image/*,audio/*,video/*,.pdf,.txt"
                onChange={(e) => pickFile(e.target.files?.[0])}
              />
              {file ? (
                <div className="flex items-center justify-center gap-3">
                  <FileText className="h-5 w-5 text-brand-400" />
                  <div className="min-w-0 text-left">
                    <p className="truncate text-sm font-medium text-ink">{file.name}</p>
                    <p className="text-2xs text-ink-muted">
                      {(file.size / 1024 / 1024).toFixed(1)} MB
                    </p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); setFile(null); }}
                    className="btn-ghost !p-1.5"
                    aria-label="Remove file"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <div className="space-y-1.5">
                  <Upload className="mx-auto h-7 w-7 text-ink-muted" />
                  <p className="text-sm font-medium text-ink">
                    Drop a file, or click to choose
                  </p>
                  <p className="text-2xs text-ink-muted">
                    Image, audio, video, PDF or text · up to {MAX_FILE_MB} MB
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-line px-5 py-4">
          <p className="text-2xs text-ink-muted">
            {busy ? status : 'Usually takes a few seconds'}
          </p>
          {busy ? (
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-brand-400" />
              <button onClick={cancel} className="btn-secondary !px-4 !py-2 text-2xs">
                Cancel
              </button>
            </div>
          ) : (
            <button onClick={submit} disabled={!ready} className="btn-primary">
              Check it
              <ArrowRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {error && <ErrorPanel error={error} onRetry={() => { setError(null); submit(); }} />}
    </div>
  );
}

function ErrorPanel({ error, onRetry }) {
  const offline = error instanceof ApiError && error.isOffline;
  const auth = error instanceof ApiError && error.isAuthError;

  return (
    <div
      className="card-flat p-4"
      style={{ boxShadow: 'inset 0 0 0 1px rgb(var(--c-critical) / 0.3)' }}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-status-critical-text" />
        <div className="min-w-0 flex-1 space-y-2">
          <p className="text-sm font-medium text-ink">
            {auth ? 'Please sign in again' : offline ? 'Cannot reach the server' : 'That did not work'}
          </p>
          <p className="text-sm text-ink-secondary">{error.message}</p>
          {!auth && (
            <button onClick={onRetry} className="btn-secondary !px-4 !py-1.5 text-2xs">
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
