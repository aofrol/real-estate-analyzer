import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary accent
        primary: {
          DEFAULT: "#1d4ed8", // blue-700
          light: "#3b82f6",  // blue-500
          dark: "#1e3a8a",   // blue-900
        },
      },
    },
  },
  plugins: [],
};

export default config;
