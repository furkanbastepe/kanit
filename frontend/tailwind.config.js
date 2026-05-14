/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        surface: "var(--surface)",
        raised: "var(--surface-raised)",
        panel: "var(--surface-panel)",
        ink: "var(--ink)",
        muted: "var(--ink-muted)",
        hairline: "var(--hairline)",
        evidence: "var(--evidence-flow)",
        risk: "var(--signal-risk)",
        critical: "var(--signal-critical)",
        verified: "var(--signal-verified)",
        focus: "var(--focus-ring)",
      },
    },
  },
  plugins: [],
};
