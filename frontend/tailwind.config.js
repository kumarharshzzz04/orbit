/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // ORBIT Design System - Dark Space Theme
        orbit: {
          // Backgrounds
          bg: {
            primary: '#030712',       // Near-black / deep navy
            secondary: '#0c1222',     // Dark blue-grey
            tertiary: '#111827',      // Elevated surfaces
            card: '#0f172a',          // Card backgrounds
          },
          // Borders
          border: {
            primary: '#1e293b',       // Subtle cool grey
            secondary: '#334155',     // Stronger borders
            focus: '#06b6d4',         // Electric cyan focus
          },
          // Accents
          accent: {
            primary: '#06b6d4',       // Electric cyan
            secondary: '#a855f7',     // Restrained violet
            positive: '#22c55e',      // Controlled green
            warning: '#f59e0b',       // Amber
            negative: '#ef4444',      // Restrained red
          },
          // Text
          text: {
            primary: '#f8fafc',       // Near white
            secondary: '#94a3b8',     // Muted
            tertiary: '#64748b',      // Subtle
            inverse: '#030712',       // On accent
          },
          // Agent colors
          agent: {
            researcher: '#06b6d4',    // Cyan
            hypothesizer: '#a855f7',  // Violet
            skeptic: '#f59e0b',       // Amber
            experimenter: '#22c55e',  // Green
            evaluator: '#ef4444',     // Red
            orchestrator: '#ec4899',  // Pink
          },
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        'display-xl': ['4.5rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
        'display-lg': ['3.75rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
        'display-md': ['3rem', { lineHeight: '1.2', letterSpacing: '-0.01em' }],
        'display-sm': ['2.25rem', { lineHeight: '1.3', letterSpacing: '-0.01em' }],
        'heading-xl': ['1.875rem', { lineHeight: '1.3' }],
        'heading-lg': ['1.5rem', { lineHeight: '1.4' }],
        'heading-md': ['1.25rem', { lineHeight: '1.4' }],
        'heading-sm': ['1.125rem', { lineHeight: '1.5' }],
        'body-lg': ['1.125rem', { lineHeight: '1.6' }],
        'body': ['1rem', { lineHeight: '1.6' }],
        'body-sm': ['0.875rem', { lineHeight: '1.5' }],
        'caption': ['0.75rem', { lineHeight: '1.5' }],
        'code': ['0.8125rem', { lineHeight: '1.6' }],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '128': '32rem',
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.5rem',
      },
      boxShadow: {
        'glow-cyan': '0 0 20px rgba(6, 182, 212, 0.3)',
        'glow-violet': '0 0 20px rgba(168, 85, 247, 0.3)',
        'glow-green': '0 0 20px rgba(34, 197, 94, 0.3)',
        'inner-glow': 'inset 0 0 20px rgba(6, 182, 212, 0.1)',
      },
      backgroundImage: {
        'grid-pattern': 'linear-gradient(rgba(148, 163, 184, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(148, 163, 184, 0.03) 1px, transparent 1px)',
        'radial-glow': 'radial-gradient(ellipse at center, rgba(6, 182, 212, 0.15) 0%, transparent 70%)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow': 'spin 3s linear infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}