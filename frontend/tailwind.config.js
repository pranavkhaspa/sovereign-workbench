/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Mapped to the CSS custom properties in index.css so utilities follow
        // the active theme (dark by default, light via [data-theme="light"]).
        ink: "var(--ink)",
        "ink-raised": "var(--ink-raised)",
        panel: "var(--panel)",
        "panel-raised": "var(--panel-raised)",
        line: "var(--line)",
        "line-soft": "var(--line-soft)",
        fg: "var(--text)",
        muted: "var(--muted)",
        accent: "var(--cyan)",
        "accent-bright": "var(--cyan-bright)",
        ok: "var(--green)",
        warn: "var(--orange)",
        danger: "var(--red)",
      },
    },
  },
  plugins: [],
};
