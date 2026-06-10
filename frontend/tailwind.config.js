/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
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
        stitch: {
          cyan: '#00f0ff',
          purple: '#bc13fe',
          emerald: '#00ff94',
          rose: '#ffb4ab',
          bg: '#101417',
          surface: '#1c2024',
          surfaceHigh: '#272a2e',
          outline: '#849495',
        },
        trust: {
          high: '#10b981',
          medium: '#f59e0b',
          low: '#ef4444',
        },
        surface: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          700: '#1e293b',
          800: '#0f172a',
          900: '#020617',
        }

      },
      fontFamily: {
        sans: ['Geist', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Satoshi', 'Geist', 'sans-serif'],
        mono: ['Geist Mono', 'JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'shimmer': 'shimmer 2s linear infinite',
        'float': 'float 6s ease-in-out infinite',
        'gauge': 'gauge 1.5s ease-out forwards',
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
        gauge: {
          '0%': { strokeDashoffset: '283' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}
