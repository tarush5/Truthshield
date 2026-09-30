import { useNavigate } from 'react-router-dom';

import { Badge, Button, Card, CardHeader, PageHeader, Skeleton } from '@/components/ui';
import { useEngines, useHealth } from '@/hooks/queries';
import { FAMILY_LABEL } from '@/lib/format';
import { authService } from '@/services';
import { useAuth } from '@/stores/auth';

export default function Settings() {
  const user = useAuth((s) => s.user);
  const refreshToken = useAuth((s) => s.refreshToken);
  const clear = useAuth((s) => s.clear);
  const engines = useEngines();
  const health = useHealth();
  const navigate = useNavigate();

  const signOut = async () => {
    if (refreshToken) await authService.logout(refreshToken).catch(() => undefined);
    clear();
    navigate('/');
  };

  return (
    <>
      <PageHeader eyebrow="Settings" title={<>Account & <span className="font-display italic">platform</span></>} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader eyebrow="Account" title={user?.email ?? '—'} />
          <div className="space-y-4 p-5 pt-4 sm:p-6 sm:pt-4 text-sm">
            <div className="flex items-center justify-between"><span className="text-muted">Role</span><Badge tone="accent">{user?.role}</Badge></div>
            <p className="text-xs leading-relaxed text-muted">
              USER and ANALYST: your own investigations (analyst-only tooling — feedback review, threat-intel curation — arrives in later phases). ADMIN: user and role management, audit log, and every investigation. Roles are checked on the server for every request.
            </p>
            <div className="flex items-center justify-between"><span className="text-muted">Session</span><span className="text-text-primary/90">Rotating refresh token</span></div>
            <Button variant="outline" size="sm" onClick={signOut}>Sign out</Button>
          </div>
        </Card>

        <Card>
          <CardHeader eyebrow="Risk engine" title="Active weights" />
          <div className="p-5 pt-4 sm:p-6 sm:pt-4">
            {engines.data ? (
              <>
                <ul className="space-y-2">
                  {Object.entries(engines.data.risk.weights).map(([family, w]) => (
                    <li key={family} className="flex items-center gap-3 text-sm">
                      <span className="w-36 text-muted">{FAMILY_LABEL[family] ?? family}</span>
                      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-stroke/60"><span className="accent-gradient block h-full" style={{ width: `${w * 4}%` }} /></span>
                      <span className="w-8 text-right font-mono text-xs tabular">{w}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-4 text-xs text-muted">Configured with RISK_WEIGHTS_JSON on the server · version {engines.data.risk.version}</p>
              </>
            ) : <Skeleton className="h-40" />}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader eyebrow="Engines" title="Registered analysis engines" />
          <div className="grid gap-3 p-5 pt-4 sm:grid-cols-3 sm:p-6 sm:pt-4">
            {engines.data?.engines.map((e) => (
              <div key={e.name} className="rounded-2xl border border-stroke p-4">
                <p className="font-mono text-sm text-text-primary">{e.name} <span className="text-muted">{e.version}</span></p>
                <Badge className="mt-2">{e.kind}</Badge>
                <p className="mt-2 text-xs text-muted">{e.describes}</p>
              </div>
            ))}
          </div>
          {health.data && (
            <p className="px-6 pb-6 text-xs text-muted">
              Offline mode: {health.data.investigations.offline_mode ? 'on' : 'off'} · evidence retrieval {health.data.investigations.evidence_retrieval ? 'enabled' : 'disabled'} · page inspection {health.data.investigations.page_fetch ? 'enabled' : 'disabled'} · languages {health.data.languages.join(', ')}
            </p>
          )}
        </Card>
      </div>
    </>
  );
}
