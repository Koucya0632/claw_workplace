import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        sand: "#f4ecd8",
        coral: "#f26b5b",
        teal: "#167d7f",
        gold: "#f0b429",
        mint: "#a7f3d0"
      },
      boxShadow: {
        pixel: "6px 6px 0 0 rgba(17, 24, 39, 0.95)"
      },
      backgroundImage: {
        "grid-fade":
          "linear-gradient(rgba(17,24,39,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(17,24,39,0.06) 1px, transparent 1px)"
      }
    }
  },
  plugins: []
};

export default config;

