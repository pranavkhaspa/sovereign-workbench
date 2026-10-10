/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b1220",
        panel: "#121a2b",
        accent: "#38bdf8",
        ok: "#22c55e",
        warn: "#f59e0b",
        danger: "#ef4444",
      },
    },
  },
  plugins: [],
};
