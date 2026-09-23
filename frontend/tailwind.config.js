/** @type {import('tailwindcss').Config} */

// Colours live as CSS custom properties in index.css and are consumed here
// through `rgb(var(--token) / <alpha-value>)`, so one token drives both
// Tailwind utilities and hand-written CSS, and the themes swap in one place.
const token = (name) => `rgb(var(${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        page: token('--c-page'),
        surface: {
          DEFAULT: token('--c-surface'),
          raised: token('--c-surface-raised'),
          sunken: token('--c-surface-sunken'),
        },
        ink: {
          DEFAULT: token('--c-ink'),
          secondary: token('--c-ink-secondary'),
          muted: token('--c-ink-muted'),
        },
        brand: {
          DEFAULT: token('--c-brand'),
          deep: token('--c-brand-deep'),
          // Steps kept for the few places that need a lighter or darker
          // brand tint than the two semantic tokens above.
          300: '#8eceff',
          400: '#59b3ff',
          500: '#3b93ff',
          600: '#1a6ff5',
        },
        // Reserved for verdict and state. Never used as a chart series, and
        // always paired with an icon or label so colour never carries the
        // meaning alone.
        status: {
          good: token('--c-good'),
          'good-text': token('--c-good-text'),
          warning: token('--c-warning'),
          'warning-text': token('--c-warning-text'),
          serious: token('--c-serious'),
          critical: token('--c-critical'),
          'critical-text': token('--c-critical-text'),
        },
        // Validated as a categorical set against the card surface: adjacent
        // CVD ΔE 8.4, normal-vision ΔE 19.8, all ≥3:1 contrast.
        series: {
          1: token('--c-series-1'),
          2: token('--c-series-2'),
          3: token('--c-series-3'),
          4: token('--c-series-4'),
        },
        line: token('--c-border'),
      },

      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        display: ['Instrument Serif', 'Georgia', 'serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },

      fontSize: {
        // The old UI leaned on 10px labels at 40% opacity, which is why whole
        // screens read as blank. 11px is the floor now.
        '2xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.01em' }],
      },

      maxWidth: {
        // A comfortable measure for body copy — roughly 68 characters at the
        // base size. Past that, the eye loses the line on return.
        prose: '34rem',
      },

      boxShadow: {
        sm: 'var(--shadow-sm)',
        DEFAULT: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        edge: 'var(--edge)',
      },

      transitionTimingFunction: {
        // Decelerating: fast to start, settles gently. Reads as responsive
        // without the overshoot of a spring.
        out: 'cubic-bezier(0.2, 0, 0.2, 1)',
      },
    },
  },
  plugins: [],
};
