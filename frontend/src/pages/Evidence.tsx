import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Database, ExternalLink, Search } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { ScoreBreakdown } from '@/components/investigation/evidence';
import {
  Badge, Button, Card, EmptyState, ErrorNotice, Input, Label, PageHeader, Select, Skeleton, Tabs, Textarea,
} from '@/components/ui';
import { formatDate, humanize, safeHref } from '@/lib/format';
import { evidenceService } from '@/services';
import { useAuth } from '@/stores/auth';

const CATEGORIES = ['OFFICIAL', 'PRIMARY', 'SECONDARY', 'COMMUNITY', 'UNKNOWN'];
type TabId = 'search' | 'sources' | 'claims' | 'ingest';

function StoreStats() {
  const { data } = useQuery({ queryKey: ['evidence-stats'], queryFn: evidenceService.stats });
  if (!data) return <Skeleton className="h-20" />;
  return (
    <Card className="flex flex-wrap items-center gap-x-8 gap-y-3 p-5">
      <Database className="h-5 w-5 text-muted" aria-hidden />
      {[['Documents', data.documents], ['Chunks', data.chunks], ['Sources', data.sources]].map(([label, value]) => (
        <div key={label as string}>
          <p className="font-display text-3xl tabular-nums text-text-primary">{(value as number).toLocaleString()}</p>
          <p className="text-[11px] uppercase tracking-[0.2em] text-muted">{label}</p>
        </div>
      ))}
      <div className="ml-auto space-y-1 text-right text-xs text-muted">
        <p>{data.backend} · reranker {data.reranker}</p>
        <p>
          embeddings <span className="font-mono">{data.embedding_model}</span>{' '}
          <Badge tone={data.embedding_kind === 'semantic' ? 'good' : 'warn'}
            title={data.embedding_kind === 'lexical' ? 'Vocabulary overlap, not meaning: no semantic model is installed' : 'Trained sentence embeddings'}>
            {data.embedding_kind}
          </Badge>
        </p>
      </div>
    </Card>
  );
}

function SearchTab() {
  const [q, setQ] = useState('');
  const [submitted, setSubmitted] = useState('');
  const [category, setCategory] = useState('');
  const { data, isFetching, error } = useQuery({
    queryKey: ['evidence-search', submitted, category],
    queryFn: () => evidenceService.search({ q: submitted, category: category ? [category] : [], limit: 15 }),
    enabled: submitted.length >= 2,
  });

  return (
    <div className="space-y-6">
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); setSubmitted(q.trim()); }} className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
          <Input aria-label="Search the evidence store" placeholder="A claim or topic, e.g. lemon water cures cancer" value={q}
            onChange={(e) => setQ(e.target.value)} className="pl-10" />
        </div>
        <Select aria-label="Source category" value={category} onChange={(e) => setCategory(e.target.value)} className="sm:w-44">
          <option value="">Any category</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{humanize(c)}</option>)}
        </Select>
        <Button type="submit" disabled={q.trim().length < 2} loading={isFetching}>Search</Button>
      </form>
      {error && <ErrorNotice error={error} />}
      {data && (
        data.results.length ? (
          <ul className="space-y-3">
            {data.results.map((r) => (
              <li key={r.chunk_id} className="rounded-2xl border border-stroke bg-surface/40 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge>{humanize(r.category)}</Badge>
                  <span className="text-xs text-muted">credibility {r.credibility.toFixed(2)}</span>
                  <span className="text-xs text-muted">· {r.content_scope === 'snippet' ? 'search snippet' : humanize(r.content_scope)}</span>
                </div>
                {safeHref(r.url) ? (
                  <a href={safeHref(r.url)} target="_blank" rel="noreferrer noopener" className="mt-2 inline-flex items-start gap-1.5 text-sm text-text-primary hover:underline">
                    {r.title || r.publisher} <ExternalLink className="mt-0.5 h-3.5 w-3.5 text-muted" aria-hidden />
                  </a>
                ) : <p className="mt-2 text-sm text-text-primary">{r.title}</p>}
                <p className="text-xs text-muted">{r.publisher} · retrieved {formatDate(r.retrieved_at)}</p>
                <blockquote className="mt-2 border-l-2 border-stroke pl-3 text-sm text-muted">{r.passage}</blockquote>
                <ScoreBreakdown scores={r.scores} />
              </li>
            ))}
          </ul>
        ) : <EmptyState title="Nothing relevant stored" body="The store grows as investigations retrieve evidence and as analysts add documents." />
      )}
      {data && (
        <p className="text-xs text-muted">
          Hybrid retrieval: {data.embedding.kind} embeddings ({data.embedding.model}) + keyword ranking, fused with reciprocal
          rank fusion and reranked by {data.reranker.name}{data.reranker.learned ? '' : ' (a transparent weighted score, not a learned model)'}.
        </p>
      )}
    </div>
  );
}

function SourcesTab() {
  const isAdmin = useAuth((s) => s.user?.role === 'ADMIN');
  const [q, setQ] = useState('');
  const [category, setCategory] = useState('');
  const client = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['sources', q, category],
    queryFn: () => evidenceService.sources({ q, category: category || undefined }),
  });
  const update = useMutation({
    mutationFn: ({ id, category: c }: { id: string; category: string }) => evidenceService.updateSource(id, { category: c }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['sources'] }),
  });

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-[1fr_12rem]">
        <Input aria-label="Filter sources by domain" placeholder="Filter by domain" value={q} onChange={(e) => setQ(e.target.value)} />
        <Select aria-label="Category" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Any category</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{humanize(c)}</option>)}
        </Select>
      </div>
      <p className="text-xs text-muted">Categories and credibility start as heuristics and are signals, never truth. {isAdmin ? 'Changing a category marks the source as curated, and it keeps that rating.' : 'Administrators can curate them.'}</p>
      {isLoading ? <Skeleton className="h-60" /> : data?.items.length ? (
        <div className="overflow-x-auto rounded-2xl border border-stroke">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="text-[11px] uppercase tracking-[0.15em] text-muted">
              <tr className="border-b border-stroke"><th className="p-3 font-normal">Domain</th><th className="p-3 font-normal">Category</th><th className="p-3 font-normal">Credibility</th><th className="p-3 font-normal">Documents</th><th className="p-3 font-normal">Last seen</th></tr>
            </thead>
            <tbody className="divide-y divide-stroke">
              {data.items.map((s) => (
                <tr key={s.id}>
                  <td className="p-3 font-mono text-xs text-text-primary">{s.domain}{s.curated && <Badge tone="accent" className="ml-2">curated</Badge>}</td>
                  <td className="p-3">
                    {isAdmin ? (
                      <Select aria-label={`Category for ${s.domain}`} value={s.category} className="!py-1.5 text-xs"
                        onChange={(e) => update.mutate({ id: s.id, category: e.target.value })}>
                        {CATEGORIES.map((c) => <option key={c} value={c}>{humanize(c)}</option>)}
                      </Select>
                    ) : <Badge>{humanize(s.category)}</Badge>}
                  </td>
                  <td className="p-3 font-mono text-xs tabular">{s.credibility.toFixed(2)}</td>
                  <td className="p-3 text-xs tabular">{s.documents}</td>
                  <td className="p-3 text-xs text-muted">{formatDate(s.last_seen_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <EmptyState title="No sources yet" body="Sources are registered as evidence is retrieved or ingested." />}
      {update.error && <ErrorNotice error={update.error} />}
    </div>
  );
}

function ClaimsTab() {
  const [q, setQ] = useState('');
  const { data, isLoading } = useQuery({ queryKey: ['claims-index', q], queryFn: () => evidenceService.claims({ q }) });
  return (
    <div className="space-y-4">
      <Input aria-label="Search claims" placeholder="Search claims extracted from your investigations" value={q} onChange={(e) => setQ(e.target.value)} />
      {isLoading ? <Skeleton className="h-40" /> : data?.items.length ? (
        <ul className="space-y-2">
          {data.items.map((c) => (
            <li key={`${c.investigation_id}-${c.claim_key}`}>
              <Link to={`/app/investigations/${c.investigation_id}`} className="flex flex-wrap items-center gap-3 rounded-2xl border border-stroke bg-surface/30 px-4 py-3 hover:bg-surface">
                <Badge tone={c.assessment === 'CONTRADICTED' ? 'bad' : c.assessment === 'SUPPORTED' ? 'good' : 'neutral'}>{humanize(c.assessment)}</Badge>
                <span className="min-w-0 flex-1 text-sm text-text-primary/90">“{c.text}”</span>
                <span className="font-mono text-xs text-muted">{c.public_id} · {c.source_count} sources</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : <EmptyState title="No claims yet" body="Claims appear here as investigations extract them." />}
    </div>
  );
}

function IngestTab() {
  const [mode, setMode] = useState<'url' | 'text'>('url');
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const client = useQueryClient();
  const ingest = useMutation({
    mutationFn: () => mode === 'url' ? evidenceService.ingest({ url }) : evidenceService.ingest({ title, text, source_url: url }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['evidence-stats'] });
      client.invalidateQueries({ queryKey: ['sources'] });
    },
  });

  return (
    <Card className="p-5 sm:p-6">
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); ingest.mutate(); }} className="space-y-4">
        <div className="flex gap-2" role="radiogroup" aria-label="Ingestion mode">
          {(['url', 'text'] as const).map((m) => (
            <button type="button" key={m} role="radio" aria-checked={mode === m} onClick={() => setMode(m)}
              className={mode === m ? 'rounded-full bg-text-primary px-4 py-2 text-sm text-bg' : 'rounded-full border border-stroke px-4 py-2 text-sm text-muted'}>
              {m === 'url' ? 'Fetch a page' : 'Paste text'}
            </button>
          ))}
        </div>
        <div>
          <Label htmlFor="ingest-url" hint={mode === 'url' ? 'Fetched server-side through the SSRF guard' : 'Required, so the evidence stays citable'}>
            {mode === 'url' ? 'Page URL' : 'Source URL'}
          </Label>
          <Input id="ingest-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.who.int/news/..." />
        </div>
        {mode === 'text' && (
          <>
            <div><Label htmlFor="ingest-title">Title</Label><Input id="ingest-title" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
            <div><Label htmlFor="ingest-text">Text</Label><Textarea id="ingest-text" rows={8} value={text} onChange={(e) => setText(e.target.value)} /></div>
          </>
        )}
        {ingest.error && <ErrorNotice error={ingest.error} />}
        {ingest.data && (
          <p className="text-sm text-risk-low">
            {ingest.data.created ? 'Added' : 'Already stored (unchanged)'}: {ingest.data.chunks} chunk{ingest.data.chunks === 1 ? '' : 's'} from {ingest.data.source?.domain}.
          </p>
        )}
        <Button type="submit" disabled={!url.trim() || (mode === 'text' && text.trim().length < 40)} loading={ingest.isPending}>Add to evidence store</Button>
      </form>
    </Card>
  );
}

export default function Evidence() {
  const role = useAuth((s) => s.user?.role);
  const canIngest = role === 'ANALYST' || role === 'ADMIN';
  const [tab, setTab] = useState<TabId>('search');
  const tabs: { id: TabId; label: string }[] = [
    { id: 'search', label: 'Search' },
    { id: 'sources', label: 'Source registry' },
    { id: 'claims', label: 'Claims' },
    ...(canIngest ? [{ id: 'ingest' as TabId, label: 'Add documents' }] : []),
  ];

  return (
    <>
      <PageHeader
        eyebrow="Evidence"
        title={<>The evidence <span className="font-display italic">store</span></>}
        description="Every passage an investigation cites lives here with its publisher, retrieval time and the scores that ranked it. Search it, inspect the sources, and — as an analyst — add trusted documents."
      />
      <div className="space-y-6">
        <StoreStats />
        <Tabs label="Evidence sections" tabs={tabs} value={tab} onChange={setTab} />
        {tab === 'search' && <SearchTab />}
        {tab === 'sources' && <SourcesTab />}
        {tab === 'claims' && <ClaimsTab />}
        {tab === 'ingest' && canIngest && <IngestTab />}
      </div>
    </>
  );
}
