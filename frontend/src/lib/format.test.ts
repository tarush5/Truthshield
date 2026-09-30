import { describe, expect, it } from 'vitest';

import { formatMs, humanize, relativeTime, safeHref, shortHash } from '@/lib/format';

describe('safeHref', () => {
  it('allows http and https', () => {
    expect(safeHref('https://who.int/x')).toBe('https://who.int/x');
    expect(safeHref('http://example.org')).toBe('http://example.org/');
  });
  it.each(['javascript:alert(1)', 'data:text/html,<script>x</script>', 'vbscript:x', 'not a url', '', null])(
    'refuses %s',
    (value) => expect(safeHref(value as string)).toBeUndefined(),
  );
});

describe('formatting', () => {
  it('humanizes enum values', () => expect(humanize('INSUFFICIENT_EVIDENCE')).toBe('Insufficient evidence'));
  it('formats durations', () => {
    expect(formatMs(87)).toBe('87 ms');
    expect(formatMs(1500)).toBe('1.5 s');
    expect(formatMs(null)).toBe('—');
  });
  it('shortens hashes', () => expect(shortHash('abcdef0123456789', 6)).toBe('abcdef…'));
  it('describes relative time', () => {
    const now = Date.parse('2026-10-01T12:00:00Z');
    expect(relativeTime('2026-10-01T11:59:50Z', now)).toBe('just now');
    expect(relativeTime('2026-10-01T10:00:00Z', now)).toBe('2h ago');
  });
});
