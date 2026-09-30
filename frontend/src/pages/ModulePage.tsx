import { CheckCircle2, CircleDashed } from 'lucide-react';
import { Navigate, useParams } from 'react-router-dom';

import { Badge, ButtonLink, Card, CardHeader, PageHeader } from '@/components/ui';
import { AVAILABILITY_LABEL, ALL_MODULES } from '@/lib/modules';

// Where the live part of a partially built module can be used today.
const LIVE_ENTRY: Record<string, { to: string; label: string }> = {
  fraud: { to: '/app/investigate?type=message', label: 'Investigate a message' },
  misinformation: { to: '/app/investigate?type=text', label: 'Check a claim' },
  rag: { to: '/app/history', label: 'Open an investigation’s evidence' },
  reports: { to: '/app/history', label: 'Export from history' },
  analytics: { to: '/app', label: 'Open the dashboard' },
  models: { to: '/app/settings', label: 'View registered engines' },
  security: { to: '/app/settings', label: 'Account and session' },
  multimodal: { to: '/app/investigate', label: 'Investigate' },
  'threat-intel': { to: '/app/url-intelligence', label: 'URL intelligence' },
};

/**
 * A module page that says what exists and what does not.
 *
 * Deliberately not a mock: a dashboard of invented deepfake detections would
 * be exactly the fabricated output this platform exists to catch.
 */
export default function ModulePage() {
  const { module: id } = useParams();
  const mod = ALL_MODULES.find((m) => m.id === id);
  if (!mod) return <Navigate to="/app" replace />;
  const entry = LIVE_ENTRY[mod.id];

  return (
    <>
      <PageHeader
        eyebrow={mod.title}
        title={mod.title}
        description={mod.summary}
        actions={
          <Badge tone={mod.availability === 'live' ? 'good' : mod.availability === 'partial' ? 'accent' : 'neutral'}>
            {AVAILABILITY_LABEL[mod.availability]}{mod.availability !== 'live' && ` · completes in Phase ${mod.phase}`}
          </Badge>
        }
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader eyebrow="Available now" title="What works today" />
          <div className="p-5 pt-4 sm:p-6 sm:pt-4">
            {mod.today.length ? (
              <ul className="space-y-3">
                {mod.today.map((t) => (
                  <li key={t} className="flex gap-3 text-sm text-text-primary/90"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-risk-low" aria-hidden />{t}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">Nothing in this module is live yet. No placeholder results are shown here, by design.</p>
            )}
            {entry && mod.today.length > 0 && <ButtonLink to={entry.to} size="sm" className="mt-6">{entry.label}</ButtonLink>}
          </div>
        </Card>
        <Card>
          <CardHeader eyebrow="Roadmap" title="In development" />
          <ul className="space-y-3 p-5 pt-4 sm:p-6 sm:pt-4">
            {mod.planned.map((p) => (
              <li key={p} className="flex gap-3 text-sm text-muted"><CircleDashed className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{p}</li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
