import { ArrowRight } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';

export const DRAFT_KEY = 'ts.draft';

/** A bare link is a URL investigation; headers make it an email. */
function guessType(content: string): 'url' | 'email' | 'message' {
  const text = content.trim();
  if (/^https?:\/\/\S+$/i.test(text) || /^[\w-]+(\.[\w-]+)+(\/\S*)?$/.test(text)) return 'url';
  if (/^from:/im.test(text) && /^subject:/im.test(text)) return 'email';
  return 'message';
}

/**
 * Paste it here, investigate it there: the text is handed to the Investigate
 * page through session storage (never the URL, where it would end up in
 * history and logs). Signing in first keeps the draft.
 */
export function CtaBand() {
  const [content, setContent] = useState('');
  const navigate = useNavigate();

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const text = content.trim();
    if (!text) return;
    try {
      sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ type: guessType(text), content: text.slice(0, 20_000) }));
    } catch {
      /* storage unavailable: the Investigate page simply opens empty */
    }
    navigate('/app/investigate');
  };

  return (
    <section aria-label="Investigate something" className="bg-brand-amber px-4 py-20 text-[#4A2600] sm:px-6 sm:py-28">
      <div className="mx-auto grid max-w-[1400px] items-center gap-10 lg:grid-cols-2">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] opacity-80">Something feels off?</p>
          <h2 className="font-display mt-3 text-[clamp(44px,6.5vw,92px)] leading-[0.9]">Paste it. Get evidence, not a guess.</h2>
          <p className="mt-4 max-w-md text-lg font-medium">A message, an email with its headers, or a link. Uploads of PDFs and screenshots are in the app.</p>
        </div>
        <form onSubmit={submit} className="rounded-[32px] bg-[#FBF5EA] p-3 shadow-[0_30px_60px_-30px_rgba(74,38,0,0.5)]">
          <label htmlFor="cta-content" className="sr-only">
            Content to investigate
          </label>
          <textarea
            id="cta-content"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={4}
            maxLength={20_000}
            placeholder="Dear customer, your account will be blocked today. Update KYC at…"
            className="w-full resize-none rounded-[24px] bg-transparent p-4 text-base font-medium text-[#1D1A16] placeholder:text-[#6E655A] focus:outline-none"
          />
          <div className="flex items-center justify-between gap-3 px-2 pb-1">
            <span className="text-xs font-medium text-[#6E655A]">Opens in the app · sign-in keeps your text</span>
            <button
              type="submit"
              disabled={!content.trim()}
              className="flex items-center gap-2 rounded-full bg-[#1D1A16] px-6 py-3 text-sm font-bold text-[#FBF5EA] transition-transform duration-300 hover:-translate-y-0.5 disabled:opacity-40"
            >
              Investigate <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
