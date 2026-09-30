import { ArrowLeft, Copy, Download, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { ClaimCard, SourceCard } from '@/components/investigation/evidence';
import { AgentActivityPanel, InvestigationTimeline, ProcessingStatus } from '@/components/investigation/process';
import { ConfidenceBadge, RiskBreakdown, RiskLevelBadge, RiskScoreCard } from '@/components/investigation/risk';
import { EntityList, GuidanceCard, SignalCard, UncertaintyList } from '@/components/investigation/signals';
import { UrlIntelCard } from '@/components/investigation/url';
import { Badge, Button, Card, CardHeader, EmptyState, ErrorNotice, Skeleton, Tabs } from '@/components/ui';
import { useDeleteInvestigation, useInvestigation } from '@/hooks/queries';
import { STATUS_LABEL, downloadBlob, formatDate, formatMs, humanize, shortHash } from '@/lib/format';
import { investigationService } from '@/services';
import type { InvestigationDetail, InvestigationResult as Result } from '@/types/api';

type TabId = 'overview' | 'evidence' | 'analysis' | 'media' | 'url' | 'financial' | 'timeline' | 'sources' | 'report';

export default function InvestigationResult() {
  const { id } = useParams();
  const { data: inv, error, isLoading } = useInvestigation(id);

  if (isLoading) return <Skeleton className="h-96" />;
  if (error || !inv) {
    return <EmptyState title="Investigation not found" body={error instanceof Error ? error.message : undefined} action={<Link className="text-sm text-muted underline" to="/app/history">Back to history</Link>} />;
  }

  return (
    <>
      <Header inv={inv} />
      {inv.status === 'FAILED' ? (
        <div className="space-y-6">
          <ErrorNotice error={new Error(inv.error ?? 'The analysis could not be completed.')} />
          <Card className="p-6"><InvestigationTimeline events={inv.timeline} /></Card>
        </div>
      ) : inv.status !== 'COMPLETED' || !inv.result ? (
        <ProcessingStatus inv={inv} />
      ) : (
        <Completed inv={inv} result={inv.result} />
      )}
    </>
  );
}

function Header({ inv }: { inv: InvestigationDetail }) {
  const navigate = useNavigate();
  const remove = useDeleteInvestigation();
  const [copied, setCopied] = useState(false);

  const exportAs = async (format: 'json' | 'csv') => {
    const blob = await investigationService.exportFile(inv.id, format);
    downloadBlob(blob, `${inv.public_id}.${format}`);
  };

  const onDelete = async () => {
    if (!window.confirm(`Delete ${inv.public_id}? The input, timeline and results are removed permanently.`)) return;
    await remove.mutateAsync(inv.id);
    navigate('/app/history');
  };

  return (
    <div className="mb-8">
      <Link to="/app/history" className="mb-6 inline-flex items-center gap-2 text-sm text-muted hover:text-text-primary">
        <ArrowLeft className="h-4 w-4" aria-hidden /> History
      </Link>
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-mono text-2xl text-text-primary sm:text-3xl">{inv.public_id}</h1>
            <button
              onClick={() => {
                navigator.clipboard?.writeText(inv.public_id);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              className="rounded-full p-1.5 text-muted hover:text-text-primary"
              aria-label="Copy investigation ID"
            >
              <Copy className="h-4 w-4" />
            </button>
            {copied && <span className="text-xs text-muted">Copied</span>}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <Badge tone={inv.status === 'COMPLETED' ? 'good' : inv.status === 'FAILED' ? 'bad' : 'accent'}>{STATUS_LABEL[inv.status]}</Badge>
            {inv.risk_level && <RiskLevelBadge level={inv.risk_level} />}
            {inv.risk_score !== null && <span className="font-mono text-sm tabular text-text-primary">{inv.risk_score}/100</span>}
            <ConfidenceBadge band={inv.confidence_band} />
            <Badge>{inv.type}</Badge>
            {inv.is_demo && <Badge tone="accent">Synthetic demo</Badge>}
            <span className="text-xs text-muted">{formatDate(inv.created_at)}</span>
          </div>
        </div>
        {inv.status === 'COMPLETED' && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => exportAs('json')}><Download className="h-4 w-4" aria-hidden /> JSON</Button>
            <Button variant="outline" size="sm" onClick={() => exportAs('csv')}><Download className="h-4 w-4" aria-hidden /> CSV</Button>
            <Button variant="outline" size="sm" onClick={onDelete} loading={remove.isPending}><Trash2 className="h-4 w-4" aria-hidden /> Delete</Button>
          </div>
        )}
      </div>
    </div>
  );
}

function Completed({ inv, result }: { inv: InvestigationDetail; result: Result }) {
  const [tab, setTab] = useState<TabId>('overview');
  const sources = useMemo(() => result.claims.flatMap((c) => c.sources ?? []), [result.claims]);
  const scoring = result.signals.filter((s) => s.points > 0);

  const tabs: { id: TabId; label: string; count?: number }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'analysis', label: 'AI analysis', count: result.signals.length },
    { id: 'evidence', label: 'Evidence', count: result.claims.length },
    { id: 'url', label: 'URL intelligence', count: result.url_intelligence.length },
    { id: 'media', label: 'Media forensics' },
    { id: 'financial', label: 'Financial analysis' },
    { id: 'timeline', label: 'Timeline', count: inv.timeline.length },
    { id: 'sources', label: 'Sources', count: sources.length },
    { id: 'report', label: 'Report' },
  ];

  return (
    <div className="space-y-6">
      <Tabs label="Investigation sections" tabs={tabs} value={tab} onChange={setTab} />

      {tab === 'overview' && (
        <div className="grid gap-6 xl:grid-cols-3">
          <div className="space-y-6 xl:col-span-2">
            <RiskScoreCard risk={result.risk} />
            <Card className="p-6">
              <p className="text-[11px] uppercase tracking-[0.25em] text-muted">Summary</p>
              <p className="mt-3 text-base leading-relaxed text-text-primary">{result.explanation.summary}</p>
              <dl className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Stat label="Classification" value={humanize(result.classification)} />
                <Stat label="Scoring signals" value={String(scoring.length)} />
                <Stat label="Evidence sources" value={String(sources.length)} />
                <Stat label="Processing time" value={formatMs(inv.processing_ms)} />
              </dl>
              {scoring.length > 0 && (
                <div className="mt-6 space-y-3">
                  <p className="text-[11px] uppercase tracking-[0.25em] text-muted">Top signals</p>
                  {scoring.slice(0, 3).map((s) => <SignalCard key={s.code} signal={s} />)}
                </div>
              )}
            </Card>
            <Card className="p-6">
              <p className="mb-4 text-[11px] uppercase tracking-[0.25em] text-muted">Recommended safety actions</p>
              <GuidanceCard guidance={result.recommended_actions} />
            </Card>
          </div>
          <div className="space-y-6">
            <Card>
              <CardHeader eyebrow="Uncertainty" title="What was not established" />
              <div className="p-5 pt-4 sm:p-6 sm:pt-4"><UncertaintyList items={result.uncertainties} /></div>
            </Card>
            <Card>
              <CardHeader eyebrow="Activity" title="What ran" />
              <div className="p-5 pt-4 sm:p-6 sm:pt-4"><AgentActivityPanel engines={result.engines} timeline={inv.timeline} /></div>
            </Card>
            {result.language && (
              <Card className="p-6">
                <p className="text-[11px] uppercase tracking-[0.25em] text-muted">Language</p>
                <p className="mt-2 text-sm text-text-primary">
                  {result.language.detected.toUpperCase()} · {result.language.script} · {result.language.method}
                  {!result.language.supported && <Badge tone="warn" className="ml-2">outside supported set</Badge>}
                </p>
                <p className="mt-1 text-xs text-muted">Original text preserved; no translation was applied.</p>
              </Card>
            )}
          </div>
        </div>
      )}

      {tab === 'analysis' && (
        <div className="space-y-6">
          <Card className="p-6"><RiskBreakdown risk={result.risk} /></Card>
          <div className="grid gap-3 lg:grid-cols-2">
            {result.signals.map((s) => <SignalCard key={`${s.engine}-${s.code}`} signal={s} />)}
          </div>
          {result.signals.length === 0 && <EmptyState title="No signals" body="None of the engines that ran produced a signal. See the uncertainty list for what was not checked." />}
          <Card>
            <CardHeader eyebrow="Extraction" title="Entities and intent" />
            <div className="space-y-5 p-5 pt-4 sm:p-6 sm:pt-4">
              <EntityList entities={result.entities} />
              {result.intents.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {result.intents.map((i) => <Badge key={i.intent} tone="warn" title={i.evidence}>{i.label}</Badge>)}
                </div>
              )}
            </div>
          </Card>
          <Card>
            <CardHeader eyebrow="Provenance" title="Model and detector outputs" />
            <div className="overflow-x-auto p-5 pt-4 sm:p-6 sm:pt-4">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead className="text-[11px] uppercase tracking-[0.15em] text-muted">
                  <tr><th className="pb-2 font-normal">Model</th><th className="pb-2 font-normal">Kind</th><th className="pb-2 font-normal">Task</th><th className="pb-2 font-normal">Confidence</th><th className="pb-2 font-normal">Input hash</th></tr>
                </thead>
                <tbody className="divide-y divide-stroke">
                  {inv.model_predictions.map((p, i) => (
                    <tr key={i}>
                      <td className="py-2 font-mono text-xs text-text-primary">{p.model_name} <span className="text-muted">{p.model_version}</span></td>
                      <td className="py-2 text-xs text-muted">{p.model_kind}</td>
                      <td className="py-2 text-xs text-muted">{p.task}</td>
                      <td className="py-2 font-mono text-xs tabular text-muted">{p.confidence ?? '—'}</td>
                      <td className="py-2 font-mono text-xs text-muted">{shortHash(p.input_sha256, 10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 text-xs text-muted">Phase 1 detectors are rule-based (kind “heuristic”). No trained-model metrics are shown because none have been measured.</p>
            </div>
          </Card>
        </div>
      )}

      {tab === 'evidence' && (
        result.claims.length ? (
          <div className="grid gap-4 lg:grid-cols-2">{result.claims.map((c) => <ClaimCard key={c.id} claim={c} />)}</div>
        ) : (
          <EmptyState title="No checkable claims" body="The text engine did not extract a factual claim from this input, so there was nothing to verify against sources." />
        )
      )}

      {tab === 'url' && (
        result.url_intelligence.length ? (
          <div className="space-y-4">{result.url_intelligence.map((u) => <UrlIntelCard key={u.url} intel={u} />)}</div>
        ) : (
          <EmptyState title="No links" body="This input contained no URLs." />
        )
      )}

      {tab === 'media' && <EmptyState title="Not applicable" body="Media forensics (images, audio, video) runs on uploaded files and arrives in Phase 3. This investigation had no media." />}
      {tab === 'financial' && <EmptyState title="Not applicable" body="Transaction anomaly detection runs on transaction exports and arrives in Phase 4. This investigation had no transaction data." />}

      {tab === 'timeline' && <Card className="p-6"><InvestigationTimeline events={inv.timeline} /></Card>}

      {tab === 'sources' && (
        sources.length ? <ul className="grid gap-3 lg:grid-cols-2">{sources.map((s) => <SourceCard key={s.url} source={s} />)}</ul>
          : <EmptyState title="No sources retrieved" body="Sources appear here when claims are checked against external evidence. See the evidence tab for why none were retrieved." />
      )}

      {tab === 'report' && <ReportTab inv={inv} result={result} />}
    </div>
  );
}

function ReportTab({ inv, result }: { inv: InvestigationDetail; result: Result }) {
  const [showOriginal, setShowOriginal] = useState(false);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader
          eyebrow="Input"
          title="Submitted content"
          action={inv.input.content ? (
            <button onClick={() => setShowOriginal((v) => !v)} className="text-xs text-muted underline hover:text-text-primary">
              {showOriginal ? 'Show masked' : 'Show original'}
            </button>
          ) : undefined}
        />
        <div className="p-5 pt-4 sm:p-6 sm:pt-4">
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-2xl border border-stroke bg-bg p-4 font-mono text-xs text-text-primary/90">
            {showOriginal ? inv.input.content : inv.input.redacted}
          </pre>
          <dl className="mt-4 space-y-1.5 text-xs">
            <div className="flex gap-3"><dt className="w-20 text-muted">SHA-256</dt><dd className="break-all font-mono text-text-primary/90">{inv.input.sha256}</dd></div>
            <div className="flex gap-3"><dt className="w-20 text-muted">Size</dt><dd className="text-text-primary/90">{inv.input.size_bytes} bytes</dd></div>
            {result.input.redactions.length > 0 && (
              <div className="flex gap-3"><dt className="w-20 text-muted">Masked</dt><dd className="text-text-primary/90">{result.input.redactions.map((r) => `${r.count}× ${humanize(r.kind)}`).join(', ')}</dd></div>
            )}
          </dl>
        </div>
      </Card>
      <Card>
        <CardHeader eyebrow="Structured result" title="Machine-readable report" />
        <div className="p-5 pt-4 sm:p-6 sm:pt-4">
          <pre className="max-h-[28rem] overflow-auto rounded-2xl border border-stroke bg-bg p-4 font-mono text-[11px] leading-relaxed text-text-primary/85">
            {JSON.stringify({ ...result, input: { ...result.input, redacted: '[see Input]' } }, null, 2)}
          </pre>
          <p className="mt-3 text-xs text-muted">{result.explanation.llm_note}</p>
        </div>
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-[0.2em] text-muted">{label}</dt>
      <dd className="mt-1 text-sm text-text-primary">{value}</dd>
    </div>
  );
}
