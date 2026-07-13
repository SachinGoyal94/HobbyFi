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
        // Backgrounds
        bg: {
          DEFAULT: '#060a13',
          secondary: '#0c1220',
        },
        panel: {
          DEFAULT: 'rgba(15, 23, 42, 0.65)',
          solid: '#0f172a',
          hover: '#1e293b',
        },
        // Borders
        line: {
          DEFAULT: 'rgba(148, 163, 184, 0.08)',
          strong: 'rgba(148, 163, 184, 0.15)',
          focus: 'rgba(6, 182, 212, 0.4)',
        },
        // Text
        text: {
          DEFAULT: '#e2e8f0',
          muted: '#94a3b8',
          dim: '#475569',
        },
        // Accents
        accent: {
          cyan: '#06b6d4',
          'cyan-muted': 'rgba(6, 182, 212, 0.15)',
          purple: '#8b5cf6',
          'purple-muted': 'rgba(139, 92, 246, 0.15)',
          green: '#34d399',
          'green-muted': 'rgba(52, 211, 153, 0.15)',
          amber: '#f59e0b',
          'amber-muted': 'rgba(245, 158, 11, 0.15)',
          red: '#ef4444',
          'red-muted': 'rgba(239, 68, 68, 0.15)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      borderRadius: {
        '2xl': '16px',
        xl: '12px',
        lg: '10px',
        md: '8px',
      },
      boxShadow: {
        glow: '0 0 20px rgba(6, 182, 212, 0.15)',
        'glow-purple': '0 0 20px rgba(139, 92, 246, 0.15)',
        'glow-amber': '0 0 20px rgba(245, 158, 11, 0.15)',
        card: '0 4px 24px -4px rgba(0, 0, 0, 0.5)',
        elevated: '0 8px 40px -8px rgba(0, 0, 0, 0.6)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-in-right': 'slideInRight 0.25s ease-out',
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
        'shimmer': 'shimmer 2s ease-in-out infinite',
        'bounce-subtle': 'bounceSoft 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        pulse: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 8px rgba(6, 182, 212, 0.2)' },
          '50%': { boxShadow: '0 0 20px rgba(6, 182, 212, 0.5)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        bounceSoft: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-4px)' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}