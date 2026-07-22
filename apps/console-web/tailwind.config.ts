import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
      },
      fontSize: {
        xs: ["0.7rem", { lineHeight: "1rem" }],
        sm: ["0.8rem", { lineHeight: "1.25rem" }],
      },
    },
  },
  plugins: [],
};

export default config;
