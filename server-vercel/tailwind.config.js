/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0b0e14',
        surface: '#10151f',
        card: '#141a24',
        'card-hover': '#19212d',
        border: '#232c39',
        accent: '#6d5efc',
        'accent-cyan': '#00c2ff',
        success: '#2ee6a6',
        danger: '#ff5c7a',
        warning: '#ffb454',
      },
    },
  },
  plugins: [],
};
