import { ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';

import { RiskLevelBadge } from '@/components/investigation/risk';
import { Badge, Spinner } from '@/components/ui';
import { STATUS_LABEL, humanize, relativeTime } from '@/lib/format';
import type { InvestigationSummary } from '@/types/api';

export function InvestigationRow({ inv }: { inv: InvestigationSummary }) {
  const running = inv.status !== 'COMPLETED' && inv.status !== 'FAILED';
  return (
    <Link
      to={`/app/investigations/${inv.id}`}
      className="group flex items-center gap-4 rounded-2xl border border-stroke bg-surface/30 px-4 py-3 transition-colors hover:bg-surface"
    >
      <div className="w-14 shrink-0 text-center">
        {running ? <Spinner className="mx-auto" /> : (
          <span className="font-display text-2xl tabular-nums text-text-primary">{inv.risk_score ?? '—'}</span>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs text-muted">{inv.public_id}</span>
          {running ? <Badge tone="accent">{STATUS_LABEL[inv.status]}</Badge> : inv.status === 'FAILED' ? <Badge tone="bad">Failed</Badge> : <RiskLevelBadge level={inv.risk_level} />}
          <Badge>{inv.type}</Badge>
          {inv.is_demo && <Badge tone="accent">demo</Badge>}
        </div>
        <p className="mt-1 truncate text-sm text-text-primary/90">{inv.excerpt || '—'}</p>
        {inv.classification && <p className="mt-0.5 text-xs text-muted">{humanize(inv.classification)}</p>}
      </div>
      <span className="hidden shrink-0 text-xs text-muted sm:block">{relativeTime(inv.created_at)}</span>
      <ChevronRight className="h-4 w-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
    </Link>
  );
}
