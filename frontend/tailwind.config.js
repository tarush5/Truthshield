/** @type {import('tailwindcss').Config} */

// Colors are declared once as CSS custom properties in index.css and consumed
// here through `rgb(var(--token) / <alpha-value>)`, so a single token drives
// both Tailwind utilities and hand-written CSS, and light/dark swap in one
// place instead of at every call site.
const token = (name) => `rgb(var(${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // ── Surfaces ──────────────────────────────────────────
        page: token('--c-page'),
        surface: {
          DEFAULT: token('--c-surface'),
          raised: token('--c-surface-raised'),
          sunken: token('--c-surface-sunken'),
          // Numeric aliases kept so existing `bg-surface-900` markup in the
          // dashboard keeps resolving while it is migrated.
          50: token('--c-surface-raised'),
          100: token('--c-surface-raised'),
          200: token('--c-surface-raised'),
          700: token('--c-surface-raised'),
          800: token('--c-surface'),
          900: token('--c-page'),
        },

        // ── Ink ───────────────────────────────────────────────
        ink: {
          DEFAULT: token('--c-ink'),
          secondary: token('--c-ink-secondary'),
          muted: token('--c-ink-muted'),
          faint: token('--c-ink-faint'),
        },

        // ── Brand ─────────────────────────────────────────────
        brand: {
          50: '#eef7ff',
          100: '#d9edff',
          200: '#bce0ff',
          300: '#8eceff',
          400: '#59b3ff',
          500: '#3b93ff',
          600: '#1a6ff5',
          700: '#1459e1',
          800: '#1748b6',
          900: '#19408f',
          950: '#142857',
        },

        // ── Status ────────────────────────────────────────────
        // Reserved for verdict/state. Never reused as a chart series.
        // Each ships with an icon + label so color never carries meaning alone.
        status: {
          good: token('--c-good'),
          'good-text': token('--c-good-text'),
          warning: token('--c-warning'),
          'warning-text': token('--c-warning-text'),
          serious: token('--c-serious'),
          critical: token('--c-critical'),
          'critical-text': token('--c-critical-text'),
        },

        // ── Chart series ──────────────────────────────────────
        // Validated as a categorical set against the app's dark card surface:
        // adjacent CVD ΔE 8.4, normal-vision ΔE 19.8, all ≥3:1 contrast.
        series: {
          1: token('--c-series-1'),
          2: token('--c-series-2'),
          3: token('--c-series-3'),
          4: token('--c-series-4'),
        },

        line: {
          DEFAULT: token('--c-border'),
          strong: token('--c-border-strong'),
        },

        // Legacy aliases still referenced by dashboard panels.
        trust: {
          high: token('--c-good'),
          medium: token('--c-warning'),
          low: token('--c-critical'),
        },
      },

      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        display: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'JetBrains Mono', 'Menlo', 'monospace'],
      },

      // A tighter type scale than Tailwind's default — the old UI leaned on
      // 10px labels at 40% opacity, which was the main legibility problem.
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.04em' }],
      },

      borderRadius: {
        '4xl': '2rem',
      },

      boxShadow: {
        card: '0 1px 2px rgba(0,0,0,0.30), 0 8px 24px -12px rgba(0,0,0,0.55)',
        lift: '0 2px 4px rgba(0,0,0,0.30), 0 20px 48px -20px rgba(0,0,0,0.70)',
        glow: '0 0 0 1px rgb(var(--c-brand) / 0.35), 0 8px 32px -8px rgb(var(--c-brand) / 0.35)',
      },

      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        shimmer: 'shimmer 2.2s linear infinite',
        float: 'float 7s ease-in-out infinite',
        'fade-up': 'fadeUp 0.5s cubic-bezier(0.22, 1, 0.36, 1) both',
        'scan': 'scan 2.4s cubic-bezier(0.4, 0, 0.2, 1) infinite',
      },

      keyframes: {
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scan: {
          '0%': { transform: 'translateY(-100%)', opacity: '0' },
          '50%': { opacity: '1' },
          '100%': { transform: 'translateY(100%)', opacity: '0' },
        },
      },

      backdropBlur: { xs: '2px' },
    },
  },
  plugins: [],
}
