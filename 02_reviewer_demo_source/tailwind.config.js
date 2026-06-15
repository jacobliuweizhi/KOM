/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#172033',
        muted: '#5f6f85',
        clinical: '#1f5673',
        teal: '#2f8f83',
        paper: '#f7f8f5'
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'Arial', 'sans-serif'],
        serif: ['Georgia', 'Times New Roman', 'serif']
      },
      boxShadow: {
        soft: '0 18px 48px rgba(23, 32, 51, 0.08)'
      }
    }
  },
  plugins: []
};
