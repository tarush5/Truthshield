# Frontend

`frontend/`: React 19 · TypeScript · Vite · Tailwind CSS 3 · Motion
(Framer Motion) · GSAP · hls.js · React Query · Zustand · Recharts ·
react-router 7.

The 1.x JSX app was retired in the 2.0 fresh start; 1.x report and share links
are rendered by the read-only `LegacyReport` page (see [MIGRATION](MIGRATION.md)).

## Design system

A single dark theme. There is no light-mode toggle.

| Token | HSL | Use |
|---|---|---|
| `--bg` | `0 0% 4%` | page |
| `--surface` | `0 0% 8%` | cards, nav pill |
| `--text` | `0 0% 96%` | primary text |
| `--muted` | `0 0% 53%` | secondary text |
| `--stroke` | `0 0% 12%` | borders, dividers |
| `--accent` | `0 0% 96%` | |

- **Accent gradient** `linear-gradient(90deg, #89AACC, #4E85BF)` (`.accent-gradient`) is used for the logo ring, hover rings, progress bars and focus.
- **Risk semantics** use a separate scale, so the accent never signals danger: LOW `#7FB59A`, MEDIUM `#D9B45A`, HIGH `#D9824E`, CRITICAL `#B8474F` (wine red). A risk colour always appears with its text label.
- **Type**: Inter (300–700) for UI; Instrument Serif italic for display moments.
- **Motion**: `scroll-down`, `role-fade-in`, `gradient-shift` keyframes. Everything respects `prefers-reduced-motion`.

Tokens are defined as bare HSL triplets and consumed as
`hsl(var(--token) / <alpha-value>)`, so Tailwind opacity modifiers
(`bg-stroke/50`) work.

## Structure

```
src/
  main.tsx, App.tsx            providers, router, page transitions
  index.css                    tokens, keyframes, utilities
  lib/                         api client (auth + refresh), format, cn
  stores/                      auth (Zustand, persisted)
  services/                    typed API calls per resource
  hooks/                       React Query hooks
  types/                       API types mirroring docs/API.md
  components/
    landing/                   LoadingScreen, Navbar, Hero, HlsVideo, Pipeline,
                               Capabilities, Principles, Explainability, Stats, Contact
    shell/                     AppShell, Sidebar, Topbar
    investigation/             RiskScoreCard, ConfidenceBadge, RiskBreakdown, SignalCard,
                               ProcessingStatus, InvestigationTimeline, AgentActivityPanel,
                               EvidenceCard, ClaimCard, UrlIntelCard, ProvenanceTag, …
    charts/                    Recharts wrappers
    ui/                        Button, GradientButton, Card, Badge, Tabs, Field, …
  pages/                       Landing, Login, Dashboard, Investigate, InvestigationResult,
                               History, UrlIntelligence, Settings, Module (planned), LegacyReport
```

## Data flow

- `lib/api.ts` is the only code that knows the wire format. It attaches the
  bearer token. On `401` it performs **one** refresh (single-flight shared by
  concurrent requests), then retries. If the refresh fails it signs out.
- React Query owns server state. A running investigation polls every 800 ms
  and stops at `COMPLETED` or `FAILED`.
- Zustand holds only client state: the session and UI preferences.

## Routes

| Path | Page | Phase |
|---|---|---|
| `/` | Landing | 1 |
| `/login` | Sign in / sign up | 1 |
| `/app` | Dashboard (real aggregates) | 1 |
| `/app/investigate` | Unified workspace (text, URL, message, email, demos) | 1 |
| `/app/investigations/:id` | Result: Overview · Signals · URL Intelligence · Evidence · Timeline · Report | 1 |
| `/app/history` | Search, filter, sort, paginate, export, delete | 1 |
| `/app/url-intelligence` | URL scanner (same pipeline, `type=url`) | 1 |
| `/app/settings` | Account, session, role | 1 |
| `/app/threat-intel`, `/fraud`, `/misinformation`, `/deepfake`, `/documents`, `/transactions`, `/evidence`, `/reports`, `/analytics`, `/models` | Module pages. Each states honestly what it will do and in which phase | 2–6 |
| `/report/:id`, `/shared/:token` | Read-only 1.x report view (keeps old links working) | 1 |

## Testing in automated browsers

Headless and background browser panes often report the document as hidden,
where `requestAnimationFrame` never fires and Motion's exit animations -- and
the route transitions that wait on them -- never complete. In development,
`localStorage.setItem('ts.skipMotion', '1')` disables transitions and the
intro (`src/lib/env.ts`). It has no effect in production builds.

## Honesty rules in the UI

- The risk score is always shown with the sentence stating what it represents, plus its confidence.
- A family that was not assessed shows *Not assessed*, never `0`.
- Each signal shows a provenance tag: Heuristic, ML model, Retrieved or LLM.
- Landing-page statistics come from `/system/health` and `/engines`, never from hard-coded numbers.
- Capabilities that are not built yet are labelled *In development* with their phase.
