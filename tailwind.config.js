/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './movies/**/*.py',
    './static/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          gold: '#F5C518',
          goldHover: '#e0b20f',
          dark: '#0c0d10',
          card: '#14161d',
          cardBorder: 'rgba(255, 255, 255, 0.08)',
          accent: '#e50914',
        }
      },
      fontFamily: {
        outfit: ['Outfit', 'sans-serif'],
        sans: ['Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
