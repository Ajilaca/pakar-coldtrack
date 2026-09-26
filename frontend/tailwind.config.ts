import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-muted": "var(--surface-muted)",
        tint: "var(--tint)",
        border: "var(--border)",
        ink: "var(--text)",
        muted: "var(--text-muted)",
        brand: { DEFAULT: "var(--brand)", strong: "var(--brand-strong)", on: "var(--on-brand)" },
        accent: { DEFAULT: "var(--accent)", soft: "var(--accent-soft)" },
        ok: { DEFAULT: "var(--ok)", soft: "var(--ok-soft)" },
        warn: { DEFAULT: "var(--warn)", soft: "var(--warn-soft)" },
        crit: { DEFAULT: "var(--crit)", soft: "var(--crit-soft)" },
      },
      borderRadius: { md: "6px", lg: "8px" },
      fontFamily: {
        sans: ["var(--font-sans)"],
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
