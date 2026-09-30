import type { Config } from 'tailwindcss';
import animate from 'tailwindcss-animate';

// Tokens are bare HSL triplets in index.css, consumed with <alpha-value> so
// opacity modifiers (bg-stroke/50, text-text-primary/80) work.
const hsl = (name: string) => `hsl(var(${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: hsl('--bg'),
        surface: hsl('--surface'),
        'text-primary': hsl('--text'),
        muted: hsl('--muted'),
        stroke: hsl('--stroke'),
        accent: hsl('--accent'),
        // Risk semantics are a separate scale from the accent, so the brand
        // colour never reads as danger. Always paired with a text label.
        risk: {
          low: hsl('--risk-low'),
          medium: hsl('--risk-medium'),
          high: hsl('--risk-high'),
          critical: hsl('--risk-critical'),
        },
      },
      fontFamily: {
        body: ['var(--font-body)'],
        display: ['var(--font-display)'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      animation: {
        'scroll-down': 'scroll-down 1.5s ease-in-out infinite',
        'role-fade-in': 'role-fade-in 0.4s ease-out',
        'gradient-shift': 'gradient-shift 6s ease infinite',
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
      },
    },
  },
  plugins: [animate],
} satisfies Config;
