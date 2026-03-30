/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        libelle: {
          indigo: '#4F46E5',
          bg: '#EEF2FF',
          emerald: '#10B981',
          rose: '#F43F5E',
          text: '#1F2937',
          surface: '#FFFFFF'
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        body: ['Roboto', 'sans-serif']
      },
      boxShadow: {
        libelle:
          '0px 3px 6px rgba(79, 70, 229, 0.05), 0px 11px 11px rgba(79, 70, 229, 0.04), 0px 25px 15px rgba(79, 70, 229, 0.03), 0px 44px 18px rgba(79, 70, 229, 0.01), 0px 69px 19px rgba(79, 70, 229, 0)'
      }
    }
  },
  plugins: []
}