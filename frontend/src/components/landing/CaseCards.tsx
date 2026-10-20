import type { ReactNode } from 'react';

import type { Case } from '@/components/landing/cases';
import { PALETTE } from '@/components/landing/palette';
import { RISK_STYLE, cn } from '@/lib/format';

/** Marks the exact words each signal quoted as its evidence. */
function highlight(text: string, signals: Case['signals'], tint: string): ReactNode {
  const needles = signals
    .map((s) => s.evidence.replace(/[…"]/g, '').trim())
    .filter((n) => n.length >= 3 && text.toLowerCase().includes(n.toLowerCase()));
  if (!needles.length) return text;
  const escaped = needles.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const pattern = new RegExp(`(${escaped.join('|')})`, 'gi');
  return text.split(pattern).map((part, i) =>
    i % 2 === 1 ? (
      <mark key={i} className="rounded-md px-0.5 text-inherit" style={{ background: tint }}>
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

export function LevelChip({ level }: { level: Case['level'] }) {
  return (
    <span className="rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide text-[#FFF6EA]" style={{ background: RISK_STYLE[level].hex }}>
      {RISK_STYLE[level].label}
    </span>
  );
}

/** The submission as the investigator saw it, evidence highlighted. */
export function MessageCard({ c, className }: { c: Case; className?: string }) {
  const p = PALETTE[c.colour];
  return (
    <div className={cn('w-[264px] rounded-[28px] bg-[#FFFDF8] p-5 text-left text-[#1D1A16] shadow-[0_30px_60px_-24px_rgba(29,26,22,0.45)] sm:w-[288px]', className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide" style={{ background: p.soft }}>
          {c.type}
        </span>
        <span className="text-[11px] font-medium text-[#6E655A]">synthetic demo</span>
      </div>
      <p className="mt-4 line-clamp-6 whitespace-pre-line text-[14px] font-medium leading-snug">{highlight(c.content, c.signals, p.soft)}</p>
      <div className="mt-5 flex items-end justify-between border-t border-[#E6DCCB] pt-4">
        <div>
          <div className="font-display text-5xl leading-none tabular">{c.score}</div>
          <div className="mt-1 text-[11px] font-medium text-[#6E655A]">risk out of 100</div>
        </div>
        <LevelChip level={c.level} />
      </div>
    </div>
  );
}

/** Where the score came from: each signal's points, summing to the total. */
export function BreakdownCard({ c, className }: { c: Case; className?: string }) {
  return (
    <div className={cn('w-[300px] rounded-[28px] bg-[#FFFDF8] p-6 text-left text-[#1D1A16] shadow-[0_30px_60px_-24px_rgba(29,26,22,0.45)]', className)}>
      <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-[#6E655A]">Risk breakdown</p>
      <div className="mt-3 flex items-end justify-between">
        <span className="font-display text-6xl leading-none tabular">{c.score}</span>
        <LevelChip level={c.level} />
      </div>
      {c.signals.length ? (
        <ul className="mt-5 space-y-3">
          {c.signals.map((s) => (
            <li key={s.title}>
              <div className="flex items-baseline justify-between gap-3 text-sm font-semibold">
                <span className="truncate">{s.title}</span>
                <span className="tabular">+{s.points}</span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[#EFE6D6]">
                <div className="h-full rounded-full bg-[#1D1A16]" style={{ width: `${Math.max(4, (s.points / Math.max(1, c.score)) * 100)}%` }} />
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-5 text-sm text-[#6E655A]">No signal scored. A low result lists what was checked; it never claims the content is safe.</p>
      )}
      <p className="mt-5 border-t border-[#E6DCCB] pt-3 text-[11px] text-[#6E655A]">Top signals shown · each point traces to its evidence</p>
    </div>
  );
}
