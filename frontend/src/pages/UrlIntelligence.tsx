import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';

import { InvestigationRow } from '@/components/investigation/InvestigationRow';
import { Button, Card, CardHeader, ErrorNotice, Input, PageHeader, Skeleton } from '@/components/ui';
import { useCreateInvestigation, useInvestigations } from '@/hooks/queries';

const CHECKS = [
  ['Lookalike domains', 'Edit-distance similarity to watched brands on the label the registrant controls.'],
  ['Structure', 'Punycode, mixed scripts, IP hosts, “@” tricks, shorteners, nested subdomains, throwaway TLDs.'],
  ['Feature vector', 'Length, entropy, digit ratio, path depth, special characters, keyword score, HTTPS.'],
  ['Page inspection', 'When enabled: SSRF-guarded fetch, redirect chain, forms posting passwords elsewhere, brand/domain mismatch. Scripts never run.'],
];

export default function UrlIntelligence() {
  const [url, setUrl] = useState('');
  const create = useCreateInvestigation();
  const recent = useInvestigations({ type: 'url', page_size: 8 });
  const navigate = useNavigate();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const created = await create.mutateAsync({ type: 'url', content: url });
    navigate(`/app/investigations/${created.id}`);
  };

  return (
    <>
      <PageHeader
        eyebrow="URL intelligence"
        title={<>Where does it <span className="font-display italic">really</span> go?</>}
        description="Paste a link. It is analysed server-side and never opened in your browser."
      />
      <Card className="mb-6 p-5 sm:p-6">
        <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
          <Input aria-label="URL to analyse" placeholder="https://secure-login.example-bank.top/verify" value={url} onChange={(e) => setUrl(e.target.value)} spellCheck={false} autoComplete="off" />
          <Button type="submit" disabled={!url.trim()} loading={create.isPending} className="shrink-0">Analyse link</Button>
        </form>
        {create.error && <ErrorNotice error={create.error} className="mt-4" />}
      </Card>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader eyebrow="Recent" title="URL investigations" />
          <div className="space-y-2 p-5 pt-4 sm:p-6 sm:pt-4">
            {recent.isLoading ? <Skeleton className="h-40" /> : recent.data?.items.length ? (
              recent.data.items.map((inv) => <InvestigationRow key={inv.id} inv={inv} />)
            ) : <p className="text-sm text-muted">No URL investigations yet.</p>}
          </div>
        </Card>
        <Card>
          <CardHeader eyebrow="Method" title="What is checked" />
          <dl className="space-y-4 p-5 pt-4 sm:p-6 sm:pt-4">
            {CHECKS.map(([t, d]) => (
              <div key={t}>
                <dt className="text-sm text-text-primary">{t}</dt>
                <dd className="mt-1 text-xs leading-relaxed text-muted">{d}</dd>
              </div>
            ))}
            <div>
              <dt className="text-sm text-text-primary">Not yet checked</dt>
              <dd className="mt-1 text-xs leading-relaxed text-muted">WHOIS age, certificates and reputation feeds. Every result lists these as uncertainty.</dd>
            </div>
          </dl>
        </Card>
      </div>
    </>
  );
}
