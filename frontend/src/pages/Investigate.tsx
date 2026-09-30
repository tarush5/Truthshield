import { FileText, Globe, Link2, Mail, MessageSquare, Play } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { Badge, Button, Card, CardHeader, ErrorNotice, Input, Label, PageHeader, Skeleton, Textarea } from '@/components/ui';
import { useCreateInvestigation, useDemos } from '@/hooks/queries';
import { cn } from '@/lib/format';
import { MODALITIES } from '@/lib/modules';
import type { InvestigationType } from '@/types/api';

const TYPES: { id: InvestigationType; label: string; icon: typeof Globe; placeholder: string; hint: string }[] = [
  { id: 'message', label: 'Message', icon: MessageSquare, placeholder: 'Paste an SMS, WhatsApp or social-media message…', hint: 'Scam categories, urgency, links and requests for codes or payment.' },
  { id: 'email', label: 'Email', icon: Mail, placeholder: 'From: …\nReply-To: …\nSubject: …\n\nPaste the email, headers included if you have them.', hint: 'Headers make sender, reply-to and display-name mismatches checkable.' },
  { id: 'url', label: 'URL', icon: Link2, placeholder: 'https://example.com/login', hint: 'Lookalike domains, structure, feature vector and page inspection.' },
  { id: 'text', label: 'Text', icon: FileText, placeholder: 'Paste an article excerpt, post or claim to check…', hint: 'Claims are extracted and checked against retrieved sources.' },
];

const MAX_CHARS = 20_000;

export default function Investigate() {
  const [params] = useSearchParams();
  const initial = (params.get('type') as InvestigationType) || 'message';
  const [type, setType] = useState<InvestigationType>(TYPES.some((t) => t.id === initial) ? initial : 'message');
  const [content, setContent] = useState('');
  const create = useCreateInvestigation();
  const demos = useDemos();
  const navigate = useNavigate();
  const current = TYPES.find((t) => t.id === type)!;

  useEffect(() => create.reset(), [type]);

  const submit = async (e?: FormEvent) => {
    e?.preventDefault();
    const created = await create.mutateAsync({ type, content });
    navigate(`/app/investigations/${created.id}`);
  };

  const runDemo = async (demoId: string) => {
    const created = await create.mutateAsync({ demo_id: demoId });
    navigate(`/app/investigations/${created.id}`);
  };

  return (
    <>
      <PageHeader
        eyebrow="Investigate"
        title={<>What looks <span className="font-display italic">suspicious</span>?</>}
        description="Submit content and TruthShield runs it through the full pipeline: extraction, detectors, evidence, risk and explanation. Your original input is stored unmodified and hashed; lists and exports use a masked copy."
      />

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <form onSubmit={submit} className="p-5 sm:p-6">
            <div className="mb-5 flex flex-wrap gap-2" role="radiogroup" aria-label="Input type">
              {TYPES.map((t) => (
                <button
                  type="button"
                  key={t.id}
                  role="radio"
                  aria-checked={type === t.id}
                  onClick={() => setType(t.id)}
                  className={cn(
                    'inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition-colors',
                    type === t.id ? 'border-transparent bg-text-primary text-bg' : 'border-stroke text-muted hover:text-text-primary',
                  )}
                >
                  <t.icon className="h-4 w-4" aria-hidden /> {t.label}
                </button>
              ))}
            </div>

            <Label htmlFor="content" hint={type !== 'url' ? `${content.length.toLocaleString()} / ${MAX_CHARS.toLocaleString()}` : undefined}>
              {current.label}
            </Label>
            {type === 'url' ? (
              <Input id="content" value={content} onChange={(e) => setContent(e.target.value)} placeholder={current.placeholder} autoComplete="off" spellCheck={false} />
            ) : (
              <Textarea
                id="content"
                rows={9}
                maxLength={MAX_CHARS}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder={current.placeholder}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && content.trim()) submit();
                }}
              />
            )}
            <p className="mt-2 text-xs text-muted">{current.hint}</p>

            {create.error && <ErrorNotice error={create.error} className="mt-4" />}

            <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
              <p className="text-xs text-muted">Links are never opened in your browser. Pages are fetched server-side through an SSRF guard, scripts never run.</p>
              <Button type="submit" disabled={!content.trim()} loading={create.isPending}>
                Start investigation
              </Button>
            </div>
          </form>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader eyebrow="One-click demos" title="Synthetic samples" />
            <div className="space-y-2 p-5 pt-4 sm:p-6 sm:pt-4">
              {demos.isLoading && Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-14" />)}
              {demos.isError && (
                <div className="space-y-3">
                  <ErrorNotice error={demos.error} />
                  <Button variant="outline" size="sm" onClick={() => demos.refetch()}>Retry</Button>
                </div>
              )}
              {demos.data?.samples.map((s) => (
                <button
                  key={s.id}
                  onClick={() => runDemo(s.id)}
                  disabled={create.isPending}
                  className="group flex w-full items-center gap-3 rounded-2xl border border-stroke px-4 py-3 text-left transition-colors hover:bg-stroke/40 disabled:opacity-50"
                >
                  <Play className="h-4 w-4 shrink-0 text-muted group-hover:text-text-primary" aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm text-text-primary">{s.title}</span>
                    <span className="block truncate text-xs text-muted">{s.description}</span>
                  </span>
                  <Badge>{s.type}</Badge>
                </button>
              ))}
              {demos.data?.planned.map((p) => (
                <div key={p.id} className="flex items-center gap-3 rounded-2xl border border-dashed border-stroke px-4 py-3 opacity-70">
                  <span className="min-w-0 flex-1 text-sm text-muted">{p.title}</span>
                  <Badge>Phase {p.phase}</Badge>
                </div>
              ))}
              {demos.data && <p className="pt-2 text-[11px] text-muted">{demos.data.note} Demos run through the real pipeline and never fetch their invented domains.</p>}
            </div>
          </Card>

          <Card>
            <CardHeader eyebrow="Inputs" title="What can be analysed" />
            <ul className="flex flex-wrap gap-2 p-5 pt-4 sm:p-6 sm:pt-4">
              {MODALITIES.map((m) => (
                <li key={m.label}>
                  <Badge tone={m.availability === 'live' ? 'good' : 'neutral'}>
                    {m.label} {m.availability === 'live' ? '· live' : `· phase ${m.phase}`}
                  </Badge>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
