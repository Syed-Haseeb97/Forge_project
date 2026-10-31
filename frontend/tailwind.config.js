/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['variant', ['.dark &', '&.dark']],
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"DM Sans"', 'sans-serif'],
        serif: ['"Libre Caslon Display"', 'serif'],
      },
      colors: {
        civic: {
          teal: '#0d3035',
          'teal-dark': '#06181b',
          'teal-light': '#16444a',
          gold: '#e8b855',
          'gold-light': '#fffaf0',
          'gold-dark': '#ba7c29',
          cream: '#f6f4ee',
          mint: '#e3f0ea',
          sage: '#347161',
          crimson: '#b04b37',
        }
      }
    }
  },
  plugins: [],
}
