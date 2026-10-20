# Frontend

`frontend/`: React 19 · TypeScript · Vite · Tailwind CSS 3 · Motion
(Framer Motion) · React Query · Zustand · react-router 7. No GSAP and no
video player: since the October 2026 redesign every effect is native CSS,
Motion, or a few lines of scroll handling.

The 1.x JSX app was retired in the 2.0 fresh start; 1.x report and share links
are rendered by the read-only `LegacyReport` page (see [MIGRATION](MIGRATION.md)).

## Design system

A warm light theme: cream paper, near-black ink, and a saturated palette used
for whole surfaces (the landing hero, the pinned section, engine cards) rather
than as accents. Inspired by the layout and interaction patterns of
playful product sites; the content, cases and copy are TruthShield's own.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#FBF5EA` cream | page |
| `--surface` | `#FFFDF8` paper | cards, panels |
| `--text` | `#1D1A16` ink | primary text, solid buttons |
| `--muted` | `hsl(33 10% 38%)` | secondary text (5.6:1 on cream) |
| `--stroke` | `hsl(38 33% 84%)` | borders, dividers |
| `--accent` | `#E8562F` orange | focus rings, active states |
| palette | orange `#E8562F` · amber `#F7A41D` · green `#5DB35A` · pink `#F07C8E` · blue `#4F5FC4` · yellow `#F4D23C` | `bg-brand-*`; landing surfaces |

- **Type:** Bricolage Grotesque throughout (400–800, loaded asynchronously).
  `.font-display` is weight 800 with tight tracking and is never italic;
  large headings are lowercase on the landing page.
- **Shapes:** pill buttons (solid ink, outlined ink, paper), 24–32 px card
  radii, pill chips with a 2 px border.
- **Risk semantics** keep their own scale, readable on cream (each ≥ 4.5:1):
  LOW `#2C7230`, MEDIUM `#9A5C00`, HIGH `#C2410C`, CRITICAL `#B3261E`, always
  with a text label.
- **Motion:** spring transitions for cards, colour cross-fades for surfaces;
  everything respects `prefers-reduced-motion`.

## Landing page

| Section | File | What it does |
|---|---|---|
| Navbar | `Navbar.tsx` | Cream pill, centred wordmark, section links, ink "Sign in / Open the app" |
| Hero | `Hero.tsx` | Carousel of six example investigations; the whole hero takes each case's colour; cards fan out; arrows, dots, keyboard, autoplay (paused on hover/focus) |
| What it catches | `Catches.tsx` | Pinned (sticky) section, one screen per case: giant lowercase title, chips, message card with evidence highlighted, risk breakdown, dot navigation, scroll progress |
| Why TruthShield | `Why.tsx` | Split panel: four design facts (12 stages, 0 LLM verdicts, 99 max, 100% of points explained) with "instead of" chips and tabbed controls |
| Big type | `BigType.tsx` | "just evidence & sources." on ink |
| Engines | `Engines.tsx` | Coloured cards for every capability with its real availability |
| FAQ | `Faq.tsx` | Native `<details>` accordion; answers match the docs |
| Call to action | `CtaBand.tsx` | Paste text, a URL or an email; it opens Investigate prefilled (handed over in session storage, never the URL) |
| Footer | `Footer.tsx` | Live system status from `/system/health`, links, giant wordmark |

**The example cases are generated, not typed.** `cases.json` comes from
`scripts/landing_cases.py`, which runs the synthetic demo samples offline
through the real engines; `tests/test_v2_landing_cases.py` fails if the
file drifts from what the engines produce. Only the one-line blurbs are
hand-written.

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
    landing/                   Navbar, Hero, Catches, Why, BigType, Engines, Faq,
                               CtaBand, Footer, CaseCards; cases.json (generated)
    shell/                     AppShell, Sidebar, Topbar
    investigation/             RiskScoreCard, ConfidenceBadge, RiskBreakdown, SignalCard,
                               ProcessingStatus, InvestigationTimeline, AgentActivityPanel,
                               EvidenceCard, ClaimCard, UrlIntelCard, ProvenanceTag, …
    charts.tsx                 dependency-free SVG area and bar charts
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

## Performance

Measured with `npm run build` (gzipped):

| | Before | After |
|---|---|---|
| Initial payload (React, entry, data, CSS) | ~149 kB | ~124 kB (CI budget 140 kB) |
| Dashboard route | 110.7 kB | 4.9 kB |
| Landing route, hero chunk + below-the-fold chunk | 56 kB + hls.js 114 kB | 5 kB + 7 kB, no video |

- **Motion** uses `LazyMotion` + `m.*` components; the animation engine
  (`lib/motion-features.ts`, ~15 kB) loads asynchronously after first paint.
  `strict` mode throws in development if a full `motion.*` component slips in.
- **Charts** are hand-written SVG (`components/charts.tsx`) instead of
  Recharts, which brought D3, Redux Toolkit and Immer for two charts. Each
  chart renders its data as a visually hidden table for screen readers.
- **No media on the landing page:** the cases are drawn in HTML and CSS, so
  there are no photos or video streams to download.
- **Fonts:** one variable family (Bricolage Grotesque), loaded asynchronously.
- **Pinned section:** CSS `position: sticky` plus one passive scroll listener
  (at most one update per animation frame); no scroll library.
- **Landing split:** the hero and navbar are one chunk (5 kB gz since the
  redesign; 33 kB before, 56 kB before that); every section below the fold is
  another (`BelowFold.tsx`, 7 kB gz), requested in parallel as soon as the
  landing module runs. GSAP (~45 kB gz) and hls.js (114 kB gz) are no longer
  dependencies.
- **First paint:** `index.html` paints a dark boot mark before any script, and
  loads Google Fonts asynchronously (`display=swap`).
- **Idle prefetch:** sign-in for visitors; shell, dashboard and investigate page
  for signed-in users (`usePrefetchNext` in `App.tsx`; skipped with Save-Data).
- **Paint cost:** no backdrop blur behind opaque surfaces or on hidden overlays.
- **Result polling** starts at 250 ms and backs off to 1.5 s: most text and URL
  investigations finish in well under a second, so results appear almost
  immediately, while long evidence runs are not polled harder than before.

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
