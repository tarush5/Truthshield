import { Plus } from 'lucide-react';

import { MessageCard } from '@/components/landing/CaseCards';
import { CASES } from '@/components/landing/cases';

/** Answers that match the documentation; nothing here promises more. */
const QUESTIONS: { q: string; a: string }[] = [
  {
    q: 'Does an AI decide whether something is a scam?',
    a: 'No. Rules, retrieval and deterministic checks produce every signal and the score. A language model, when one is configured, may write a plain-language summary of those findings; it sees only the findings, never your raw input, and cannot change the result.',
  },
  {
    q: 'What does the risk score mean?',
    a: 'It estimates how likely the content is part of fraud, phishing or manipulation, from the signals listed under it, and it stops at 99 because no set of signals is proof. Confidence is a separate number, and a low score lists what was checked rather than calling anything safe.',
  },
  {
    q: 'What is not checked yet?',
    a: 'Domain age, certificates and reputation feeds for links; pixel-level image forensics, deepfakes, audio and video. Every result lists what it could not check, and the app labels each unbuilt feature with its phase.',
  },
  {
    q: 'Which languages does it understand?',
    a: 'English, Hindi (including Hinglish written in Latin script) and Tamil. Other languages are analysed with a stated limitation.',
  },
  {
    q: 'What happens to what I submit?',
    a: 'It is stored for your account with its SHA-256 fingerprint. Lists and exports use a copy with card numbers, codes and phone numbers masked, and deleting an investigation removes everything linked to it.',
  },
  {
    q: 'How accurate is it?',
    a: 'The detectors are rules, checked against labelled test sets written for the project. On sets they had not seen, recall was 0.71 to 0.77 with few or no false alarms before fixes. Those are regression checks, not real-world accuracy figures.',
  },
];

export function Faq() {
  const c = CASES.find((x) => x.id === 'prize-scam') ?? CASES[0];
  return (
    <section id="faq" aria-label="Frequently asked questions" className="bg-bg px-4 pb-24 sm:px-6 sm:pb-32">
      <div className="mx-auto grid max-w-[1400px] gap-12 lg:grid-cols-[1fr_1.4fr]">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-muted">FAQ</p>
          <h2 className="font-display mt-3 text-[clamp(48px,7vw,104px)] leading-[0.88]">Good questions.</h2>
          <p className="mt-4 max-w-xs text-lg font-medium text-muted">Anything else? The documentation answers it in full.</p>
          <div className="mt-10 hidden -rotate-6 lg:block">
            <MessageCard c={c} />
          </div>
        </div>
        <div className="divide-y divide-stroke border-y border-stroke">
          {QUESTIONS.map((item) => (
            <details key={item.q} className="group py-1">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-6 py-5 text-lg font-semibold [&::-webkit-details-marker]:hidden">
                {item.q}
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-text-primary text-bg transition-transform duration-300 group-open:rotate-45">
                  <Plus className="h-4 w-4" />
                </span>
              </summary>
              <p className="max-w-2xl pb-6 text-base font-medium leading-relaxed text-muted">{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
