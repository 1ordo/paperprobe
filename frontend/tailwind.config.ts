import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          0: "#0c0d10",
          1: "#12131a",
          2: "#1a1b24",
          3: "#22232e",
          4: "#2a2c38",
        },
        border: {
          DEFAULT: "#2a2c38",
          subtle: "#1e1f2a",
          focus: "#4f8fff",
        },
        text: {
          primary: "#e8eaed",
          secondary: "#9ca3af",
          tertiary: "#6b7280",
          inverse: "#0c0d10",
        },
        accent: {
          DEFAULT: "#4f8fff",
          hover: "#6ba1ff",
          muted: "#4f8fff20",
        },
        cosmin: {
          very_good: "#92D050",
          adequate: "#00B0F0",
          doubtful: "#FFC000",
          inadequate: "#FF0000",
          na: "#6b7280",
        },
      },
      fontFamily: {
        sans: ['"DM Sans"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      boxShadow: {
        glow: "0 0 20px rgba(79, 143, 255, 0.15)",
        "card": "0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.03)",
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.3s ease-out",
        "pulse-slow": "pulse 3s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        slideUp: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
