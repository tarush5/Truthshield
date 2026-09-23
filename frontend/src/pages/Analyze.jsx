import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle, ArrowRight, Check, FileText, Link2, Loader2, Upload, X,
} from 'lucide-react';

import { ApiError, analyzeStream, api, pollReport } from '../lib/api';

/**
 * The submission surface, and the live console that runs underneath it.
 *
 * The console shows what the server is actually doing, streamed over SSE with
 * the elapsed time the server reported. The previous version ran a timer that
 * advanced fake stage labels on a fixed interval — it showed "Verifying"
 * while the request was still queued and reached the last stage before any
 * result existed. Everything below is either a real event or a bare spinner.
 */

const MODES = [
  { id: 'text', label: 'Text', icon: FileText, hint: 'Paste a claim or an article' },
  { id: 'url', label: 'Link', icon: Link2, hint: 'We fetch the page and read it' },
  { id: 'file', label: 'File', icon: Upload, hint: 'Image, audio, video, PDF' },
];

// Mirrors the pipeline's own stage names. A stage the server reports that we
// do not know about still renders rather than being dropped.
const STAGES = [
  { id: 'ingest', label: 'Read submission' },
  { id: 'detect', label: 'Check for manipulation' },
  { id: 'verify', label: 'Find and weigh evidence' },
  { id: 'score', label: 'Reach a verdict' },
];

const MAX_FILE_MB = 25;
const SAMPLES = [
  'Drinking bleach cures COVID-19 within 24 hours.',
  'The Great Wall of China is visible from space.',
  '5G towers spread the coronavirus through radio waves.',
];

export default function Analyze() {
  const navigate = useNavigate();

  const [mode, setMode] = useState('text');
  const [text, setText] = useState('');
  const [url, setUrl] = useState('');
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);

  const [busy, setBusy] = useState(false);
  const [events, setEvents] = useState([]);
  const [claims, setClaims] = useState([]);
  const [error, setError] = useState(null);

  const fileInput = useRef(null);
  const abort = useRef(null);
  const textArea = useRef(null);

  const ready =
    (mode === 'text' && text.trim().length >= 15) ||
    (mode === 'url' && url.trim().length > 4) ||
    (mode === 'file' && Boolean(file));

  const pickFile = useCallback((chosen) => {
    if (!chosen) return;
    if (chosen.size > MAX_FILE_MB * 1024 * 1024) {
      setError(new Error(`That file is larger than the ${MAX_FILE_MB} MB limit.`));
      return;
    }
    setError(null);
    setFile(chosen);
  }, []);

  const submit = useCallback(async () => {
    if (!ready || busy) return;

    setBusy(true);
    setError(null);
    setEvents([]);
    setClaims([]);
    abort.current = new AbortController();

    try {
      // Text and links stream. Files go through the blocking endpoint, since
      // a multipart body cannot ride alongside a streamed response.
      if (mode === 'file') {
        setEvents([{ stage: 'ingest', message: 'Uploading file', progress: 0.05, elapsed: 0 }]);
        const result = await api.analyze({ file, signal: abort.current.signal });
        if (result.status === 'queued') {
          setEvents((prev) => [...prev, {
            stage: 'verify', message: 'Queued to a worker', progress: 0.4, elapsed: 0,
          }]);
          await pollReport(result.id, { signal: abort.current.signal });
        }
        navigate(`/report/${result.id}`);
        return;
      }

      const report = await analyzeStream({
        text: mode === 'text' ? text.trim() : undefined,
        url: mode === 'url' ? url.trim() : undefined,
        signal: abort.current.signal,
        on: {
          stage: (e) => setEvents((prev) => [...prev, e]),
          claim: (c) => setClaims((prev) => [...prev, c]),
        },
      });

      // Let the finished console state register rather than snapping away the
      // instant the last event lands.
      setTimeout(() => navigate(`/report/${report.id}`), 450);
    } catch (err) {
      if (err.name === 'AbortError') return;
      setError(err);
      setBusy(false);
    }
  }, [ready, busy, mode, text, url, file, navigate]);

  // ⌘/Ctrl + Enter submits from inside the textarea, where Enter is a newline.
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        submit();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [submit]);

  const cancel = () => {
    abort.current?.abort();
    setBusy(false);
    setEvents([]);
    setClaims([]);
  };

  const latest = events[events.length - 1];

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-5 sm:px-8">
      <header className="rise space-y-3 text-center">
        <span className="eyebrow justify-center">Check a claim</span>
        <h1 className="display text-4xl sm:text-5xl">Is this true?</h1>
        <p className="mx-auto max-w-prose text-sm leading-relaxed text-ink-secondary">
          You'll get a verdict, every source behind it, and an explicit list of
          anything that couldn't be checked.
        </p>
      </header>

      <div className="rise rise-1 card overflow-hidden">
        <div role="tablist" aria-label="What are you checking?" className="flex border-b border-line">
          {MODES.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              role="tab"
              aria-selected={mode === id}
              disabled={busy}
              onClick={() => { setMode(id); setError(null); }}
              className="segment flex-1 disabled:opacity-50"
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>

        <div className="p-5">
          {mode === 'text' && (
            <div className="space-y-3">
              <label htmlFor="claim" className="sr-only">Claim to check</label>
              <textarea
                id="claim"
                ref={textArea}
                rows={5}
                value={text}
                disabled={busy}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste the claim, post, or article text…"
                className="input-field resize-y"
              />
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-2xs text-ink-muted">Try:</span>
                {SAMPLES.map((sample) => (
                  <button
                    key={sample}
                    disabled={busy}
                    onClick={() => { setText(sample); textArea.current?.focus(); }}
                    className="rounded-lg border border-line px-2 py-1 text-2xs text-ink-secondary transition-colors hover:border-brand/40 hover:text-ink disabled:opacity-50"
                  >
                    {sample.length > 32 ? `${sample.slice(0, 32)}…` : sample}
                  </button>
                ))}
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
                className="input-field font-mono text-[0.8125rem]"
              />
              <p className="text-2xs text-ink-muted">
                Links to private or internal addresses are refused.
              </p>
            </div>
          )}

          {mode === 'file' && (
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files?.[0]); }}
              onClick={() => !busy && fileInput.current?.click()}
              className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition-colors ${
                dragging ? 'border-brand bg-brand/10' : 'border-line hover:bg-line/[0.03]'
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
                  <FileText className="h-5 w-5 text-brand" />
                  <div className="min-w-0 text-left">
                    <p className="truncate text-sm font-medium text-ink">{file.name}</p>
                    <p className="tnum text-2xs text-ink-muted">
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
                  <p className="text-sm font-medium text-ink">Drop a file, or click to choose</p>
                  <p className="text-2xs text-ink-muted">
                    Image, audio, video, PDF or text · up to {MAX_FILE_MB} MB
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-line px-5 py-3.5">
          <p className="text-2xs text-ink-muted">
            {busy ? latest?.message ?? 'Starting' : MODES.find((m) => m.id === mode)?.hint}
          </p>
          {busy ? (
            <button onClick={cancel} className="btn-secondary !px-4 !py-2 text-2xs">
              Cancel
            </button>
          ) : (
            <button onClick={submit} disabled={!ready} className="btn-primary">
              Check it
              <kbd className="ml-0.5 hidden rounded border border-white/25 px-1 font-mono text-[10px] opacity-80 sm:inline">
                ⌘↵
              </kbd>
              <ArrowRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {busy && <Console events={events} claims={claims} />}
      {error && <ErrorPanel error={error} onRetry={() => { setError(null); submit(); }} />}
    </div>
  );
}

/**
 * The live console.
 *
 * Elapsed times come from the server, not a local clock, so what is shown is
 * what actually happened rather than how long the browser has been waiting.
 */
function Console({ events, claims }) {
  const seen = new Map();
  events.forEach((e) => seen.set(e.stage, e));
  const progress = events[events.length - 1]?.progress ?? 0;
  const elapsed = events[events.length - 1]?.elapsed ?? 0;

  return (
    <div className="rise card overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-5 py-2.5">
        <span className="section-label">Analysis</span>
        <span className="tnum font-mono text-2xs text-ink-muted">{elapsed.toFixed(1)}s</span>
      </div>

      <div className="progress-bar !h-0.5 !rounded-none">
        <div
          className="progress-fill"
          style={{ width: `${progress * 100}%`, background: 'rgb(var(--c-brand))' }}
        />
      </div>

      <ul className="divide-y divide-line">
        {STAGES.map(({ id, label }) => {
          const event = seen.get(id);
          const done = event && progress > (event.progress ?? 0);
          const active = event && !done;

          return (
            <li key={id} className="flex items-center gap-3 px-5 py-2.5">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center">
                {done ? (
                  <Check className="h-3.5 w-3.5 text-status-good-text" />
                ) : active ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-brand" />
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-line/30" />
                )}
              </span>

              <span className={`flex-1 text-sm ${event ? 'text-ink' : 'text-ink-muted'}`}>
                {event?.message ?? label}
              </span>

              {event && (
                <span className="tnum font-mono text-2xs text-ink-muted">
                  {event.elapsed.toFixed(2)}s
                </span>
              )}
            </li>
          );
        })}
      </ul>

      {/* Claims appear as the server settles them, so a multi-claim
          submission shows progress instead of one long silence. */}
      {claims.length > 0 && (
        <div className="space-y-1.5 border-t border-line px-5 py-3">
          {claims.map((claim, i) => (
            <div key={i} className="flex items-center gap-2 text-2xs">
              <span className="badge badge-info shrink-0">{claim.verdict}</span>
              <span className="truncate text-ink-secondary">{claim.text}</span>
            </div>
          ))}
        </div>
      )}
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
