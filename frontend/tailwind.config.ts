import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        ink: "hsl(var(--ink))",
        "ink-2": "hsl(var(--ink-2))",
        /* palet mentah Ocean Blue — dipakai untuk gradien & aksen */
        "ocean-deep": "hsl(var(--ocean-deep))",
        ocean: "hsl(var(--ocean))",
        "ocean-light": "hsl(var(--ocean-light))",
        brand: {
          DEFAULT: "hsl(var(--brand))",
          soft: "hsl(var(--brand-soft))",
        },
        coral: {
          DEFAULT: "hsl(var(--coral))",
          soft: "hsl(var(--coral-soft))",
        },
        mint: {
          DEFAULT: "hsl(var(--mint))",
          soft: "hsl(var(--mint-soft))",
        },
        amberwarn: {
          DEFAULT: "hsl(var(--amber-warn))",
          soft: "hsl(var(--amber-warn-soft))",
        },
        critical: {
          DEFAULT: "hsl(var(--critical))",
          soft: "hsl(var(--critical-soft))",
        },
      },
      /* Sudut dinaikkan mengikuti gaya iOS 26 — lengkung besar dan lembut.
         xl untuk kontrol di dalam kartu, 2xl untuk kartu, 3xl untuk
         cangkang terluar (sidebar & wadah isi). */
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        xl: "0.9rem",
        "2xl": "1.5rem",
        "3xl": "2.25rem",
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      boxShadow: {
        frost: "0 2px 10px -2px rgb(15 42 67 / 0.06), 0 10px 30px -12px rgb(15 42 67 / 0.10)",
        "frost-lg": "0 8px 24px -6px rgb(15 42 67 / 0.10), 0 24px 48px -18px rgb(15 42 67 / 0.16)",
      },
      backgroundImage: {
        "frost-dots": "radial-gradient(circle, hsl(var(--brand) / 0.10) 1px, transparent 1.4px)",
      },
      backgroundSize: {
        "frost-dots": "16px 16px",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
