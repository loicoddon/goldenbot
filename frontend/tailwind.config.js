/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        gold: {
          DEFAULT: '#FFD700',
          dark: '#B8860B',
          light: '#FFF4B0',
        },
        bg: {
          DEFAULT: '#0B0F19',
          card: '#131826',
          accent: '#1B2235',
        },
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
