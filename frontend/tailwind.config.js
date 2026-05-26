/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        sentinel: {
          50:  "#eff6ff",
          500: "#1f4e79",
          700: "#163a5f",
        },
      },
    },
  },
  plugins: [],
};
