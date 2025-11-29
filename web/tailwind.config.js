/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'dark': {
          DEFAULT: '#0f172a',
          panel: '#1e293b',
          border: '#334155',
        },
        'text': {
          main: '#f1f5f9',
          muted: '#94a3b8',
        },
      },
    },
  },
  plugins: [],
}
