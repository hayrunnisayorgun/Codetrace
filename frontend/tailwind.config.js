/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        darkBg: "#0d1117",
        panelBg: "#161b22",
        borderColor: "#30363d",
        accentBlue: "#58a6ff",
        accentGreen: "#3fb950"
      }
    },
  },
  plugins: [],
}
