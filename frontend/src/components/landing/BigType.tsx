import { MessageCard } from '@/components/landing/CaseCards';
import { CASES } from '@/components/landing/cases';

/** The whole report, in three words: evidence, sources, nothing else. */
export function BigType() {
  const c = CASES.find((x) => x.id === 'suspicious-url') ?? CASES[0];
  return (
    <section aria-label="What a report contains" className="relative overflow-hidden bg-[#1D1A16] px-4 py-24 text-center sm:py-32">
      <div className="relative mx-auto max-w-[1400px]">
        <p className="font-display text-[clamp(64px,14vw,230px)] leading-[0.82] text-[#FBF5EA]">just evidence</p>
        <p className="font-display text-[clamp(64px,14vw,230px)] leading-[0.82] text-brand-amber">&amp; sources.</p>
        <div className="pointer-events-none absolute left-1/2 top-1/2 hidden -translate-x-1/2 -translate-y-1/2 -rotate-6 md:block" aria-hidden>
          <MessageCard c={c} />
        </div>
      </div>
      <p className="mx-auto mt-14 max-w-md text-lg font-medium text-[#FBF5EA]/80">
        Signals, sources, and a list of what was not checked. That is the whole report.
      </p>
    </section>
  );
}
