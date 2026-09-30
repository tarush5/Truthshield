import { ChevronLeft, ChevronRight, Download, Search, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { RiskLevelBadge } from '@/components/investigation/risk';
import { Badge, ButtonLink, EmptyState, ErrorNotice, IconButton, Input, PageHeader, Select, Skeleton, Spinner } from '@/components/ui';
import { useDeleteInvestigation, useInvestigations } from '@/hooks/queries';
import { STATUS_LABEL, downloadBlob, formatDate, humanize } from '@/lib/format';
import { investigationService } from '@/services';

const PAGE_SIZE = 20;

export default function History() {
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get('q') ?? '');
  const q = params.get('q') ?? '';
  const status = params.get('status') ?? '';
  const risk_level = params.get('risk') ?? '';
  const type = params.get('type') ?? '';
  const sort = params.get('sort') ?? '-created_at';
  const page = Number(params.get('page') ?? '1') || 1;

  const { data, isLoading, isFetching, error } = useInvestigations({ q, status, risk_level, type, sort, page, page_size: PAGE_SIZE });
  const remove = useDeleteInvestigation();

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
    setParams(next, { replace: true });
  };

  // Debounced search, kept in the URL so a filtered view can be linked.
  useEffect(() => {
    const t = setTimeout(() => search !== q && update('q', search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  const onDelete = async (id: string, publicId: string) => {
    if (window.confirm(`Delete ${publicId} and everything derived from it?`)) await remove.mutateAsync(id);
  };

  const onExport = async (id: string, publicId: string) => {
    downloadBlob(await investigationService.exportFile(id, 'json'), `${publicId}.json`);
  };

  return (
    <>
      <PageHeader
        eyebrow="Investigation history"
        title={<>Every <span className="font-display italic">case</span></>}
        description="Search by investigation ID, a phrase from the (masked) excerpt, a classification or an input SHA-256."
        actions={<ButtonLink to="/app/investigate" size="sm">New investigation</ButtonLink>}
      />

      <div className="mb-6 grid gap-3 md:grid-cols-[1fr_repeat(4,minmax(0,10rem))]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
          <Input aria-label="Search investigations" placeholder="TS-2026-000042, phrase or hash…" value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" />
        </div>
        <Select aria-label="Risk level" value={risk_level} onChange={(e) => update('risk', e.target.value)}>
          <option value="">Any risk</option>
          {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((l) => <option key={l} value={l}>{humanize(l)}</option>)}
        </Select>
        <Select aria-label="Type" value={type} onChange={(e) => update('type', e.target.value)}>
          <option value="">Any type</option>
          {['text', 'url', 'message', 'email'].map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
        </Select>
        <Select aria-label="Status" value={status} onChange={(e) => update('status', e.target.value)}>
          <option value="">Any status</option>
          {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <Select aria-label="Sort" value={sort} onChange={(e) => update('sort', e.target.value)}>
          <option value="-created_at">Newest first</option>
          <option value="created_at">Oldest first</option>
          <option value="-risk_score">Highest risk</option>
          <option value="risk_score">Lowest risk</option>
        </Select>
      </div>

      {error && <ErrorNotice error={error} className="mb-6" />}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-20" />)}</div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title={q || status || risk_level || type ? 'No matches' : 'No investigations yet'}
          body={q || status || risk_level || type ? 'Try a different search or clear the filters.' : 'Investigations you run appear here.'}
          action={<ButtonLink to="/app/investigate" variant="outline" size="sm">Start one</ButtonLink>}
        />
      ) : (
        <>
          <ul className="space-y-2">
            {data.items.map((inv) => {
              const running = inv.status !== 'COMPLETED' && inv.status !== 'FAILED';
              return (
                <li key={inv.id} className="flex items-center gap-2 rounded-2xl border border-stroke bg-surface/30 pr-2 transition-colors hover:bg-surface">
                  <Link to={`/app/investigations/${inv.id}`} className="flex min-w-0 flex-1 items-center gap-4 px-4 py-3">
                    <span className="w-12 shrink-0 text-center font-display text-2xl tabular-nums text-text-primary">
                      {running ? <Spinner className="mx-auto" /> : inv.risk_score ?? '—'}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs text-muted">{inv.public_id}</span>
                        {running ? <Badge tone="accent">{STATUS_LABEL[inv.status]}</Badge> : inv.status === 'FAILED' ? <Badge tone="bad">Failed</Badge> : <RiskLevelBadge level={inv.risk_level} />}
                        <Badge>{inv.type}</Badge>
                        {inv.is_demo && <Badge tone="accent">demo</Badge>}
                      </span>
                      <span className="mt-1 block truncate text-sm text-text-primary/90">{inv.excerpt}</span>
                      <span className="mt-0.5 block text-xs text-muted">{humanize(inv.classification)} · {formatDate(inv.created_at)}</span>
                    </span>
                  </Link>
                  {inv.status === 'COMPLETED' && (
                    <IconButton onClick={() => onExport(inv.id, inv.public_id)} aria-label={`Export ${inv.public_id} as JSON`} title="Export JSON">
                      <Download className="h-4 w-4" />
                    </IconButton>
                  )}
                  <IconButton onClick={() => onDelete(inv.id, inv.public_id)} aria-label={`Delete ${inv.public_id}`} title="Delete">
                    <Trash2 className="h-4 w-4" />
                  </IconButton>
                </li>
              );
            })}
          </ul>

          <div className="mt-6 flex items-center justify-between text-sm text-muted">
            <span>
              {data.total} investigation{data.total === 1 ? '' : 's'} {isFetching && <Spinner className="ml-2 inline h-3 w-3" />}
            </span>
            <div className="flex items-center gap-2">
              <IconButton disabled={page <= 1} onClick={() => update('page', String(page - 1))} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></IconButton>
              <span className="tabular">{page} / {pages}</span>
              <IconButton disabled={page >= pages} onClick={() => update('page', String(page + 1))} aria-label="Next page"><ChevronRight className="h-4 w-4" /></IconButton>
            </div>
          </div>
        </>
      )}
    </>
  );
}
