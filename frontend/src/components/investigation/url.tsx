import { Badge } from '@/components/ui';
import { humanize } from '@/lib/format';
import type { UrlIntel } from '@/types/api';

const FEATURE_ORDER = [
  'url_length', 'domain_length', 'subdomain_count', 'path_depth', 'special_character_count',
  'encoded_character_count', 'query_param_count', 'digit_ratio', 'entropy', 'https',
  'suspicious_keyword_score', 'brand_similarity',
];

const FETCH_TONE = { fetched: 'good', skipped: 'neutral', blocked: 'warn', failed: 'bad' } as const;

export function UrlIntelCard({ intel }: { intel: UrlIntel }) {
  const page = intel.page;
  return (
    <article className="rounded-3xl border border-stroke bg-surface/50 p-5 sm:p-6">
      <p className="break-all font-mono text-sm text-text-primary">{intel.url}</p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <Badge>host {intel.host}</Badge>
        <Badge tone="accent">registered {intel.registrable_domain}</Badge>
        {intel.closest_brand && <Badge tone="warn">closest brand: {intel.closest_brand}</Badge>}
        <Badge tone={FETCH_TONE[intel.fetch.status]}>
          page {intel.fetch.status}
          {intel.fetch.cached ? ' (cached)' : ''}
        </Badge>
      </div>
      {intel.fetch.reason && <p className="mt-2 text-xs text-muted">{intel.fetch.reason}</p>}

      <div className="mt-5 grid gap-6 lg:grid-cols-2">
        <div>
          <p className="mb-2 text-[11px] uppercase tracking-[0.2em] text-muted">Feature vector</p>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-stroke">
              {FEATURE_ORDER.filter((k) => k in intel.features).map((k) => (
                <tr key={k}>
                  <td className="py-1.5 font-mono text-xs text-muted">{k}</td>
                  <td className="py-1.5 text-right font-mono text-xs tabular text-text-primary">{intel.features[k]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <p className="mb-2 text-[11px] uppercase tracking-[0.2em] text-muted">Page inspection (static, no scripts run)</p>
          {page ? (
            <dl className="space-y-2 text-sm">
              <Row label="Final URL" value={page.final_url} mono />
              {page.redirect_chain.length > 1 && <Row label="Redirects" value={page.redirect_chain.join(' → ')} mono />}
              <Row label="Title" value={page.title ?? '—'} />
              <Row label="Forms" value={`${page.forms?.length ?? 0} (${page.password_fields ?? 0} with password)`} />
              <Row label="External scripts" value={(page.external_script_hosts ?? []).join(', ') || 'none'} mono />
              <Row label="Links" value={`${page.link_count ?? 0} · ${Math.round((page.external_link_ratio ?? 0) * 100)}% external`} />
            </dl>
          ) : (
            <p className="text-sm text-muted">The page was not retrieved, so its content and forms were not examined.</p>
          )}
          {intel.signals.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-1.5">
              {intel.signals.map((s) => <Badge key={s}>{humanize(s)}</Badge>)}
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-3">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className={mono ? 'break-all font-mono text-xs text-text-primary/90' : 'text-text-primary/90'}>{value}</dd>
    </div>
  );
}
