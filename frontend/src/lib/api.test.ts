import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, describeError, request } from '@/lib/api';
import { useAuth } from '@/stores/auth';

const user = { id: 'u', email: 'a@b.c', org_id: null, role: 'USER' as const };

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

describe('describeError', () => {
  it('prefers the 2.0 error envelope', () => {
    expect(describeError(404, { error: { code: 'NOT_FOUND', message: 'Gone', request_id: 'r1' } }))
      .toEqual({ code: 'NOT_FOUND', message: 'Gone', requestId: 'r1' });
  });
  it('falls back to the 1.x detail string', () => {
    expect(describeError(400, { detail: 'Bad' }).message).toBe('Bad');
  });
});

describe('request', () => {
  beforeEach(() => {
    useAuth.setState({ accessToken: 'old', refreshToken: 'tsr_refresh', user });
  });
  afterEach(() => vi.restoreAllMocks());

  it('refreshes once on 401, concurrently, and retries', async () => {
    let refreshCalls = 0;
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith('/auth/refresh')) {
        refreshCalls += 1;
        return json(200, { access_token: 'new', token_type: 'bearer', expires_in: 3600, refresh_token: 'tsr_next', user });
      }
      const auth = (init?.headers as Record<string, string>).Authorization;
      return auth === 'Bearer new' ? json(200, { ok: true }) : json(401, { error: { code: 'UNAUTHENTICATED', message: 'x', request_id: 'r' } });
    });

    const results = await Promise.all([request('/a'), request('/b'), request('/c')]);
    expect(results).toEqual([{ ok: true }, { ok: true }, { ok: true }]);
    expect(refreshCalls).toBe(1);
    expect(useAuth.getState().refreshToken).toBe('tsr_next');
  });

  it('signs out when the refresh is rejected', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => json(401, { error: { code: 'INVALID_REFRESH_TOKEN', message: 'ended', request_id: 'r' } }));
    await expect(request('/a')).rejects.toBeInstanceOf(ApiError);
    expect(useAuth.getState().accessToken).toBeNull();
  });

  it('reports an unreachable server as offline', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('network'));
    await expect(request('/a')).rejects.toMatchObject({ status: 0, code: 'OFFLINE' });
  });
});
