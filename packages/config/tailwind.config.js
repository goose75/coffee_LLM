/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [],
  theme: {
    extend: {
      colors: {
        // Brand palette — warm espresso tones
        bean: {
          50: "#faf7f2",
          100: "#f2ece0",
          200: "#e3d5be",
          300: "#cfb68e",
          400: "#c8a97e",
          500: "#b8924a",
          600: "#9e7a3a",
          700: "#7d5f2e",
          800: "#5c4422",
          900: "#3d2d16",
        },
        roast: {
          50: "#f8f5f0",
          100: "#ede5d8",
          200: "#d9c9af",
          300: "#bfa47e",
          400: "#a67f52",
          500: "#8c6438",
          600: "#6e4c28",
          700: "#52381c",
          800: "#382612",
          900: "#1e1408",
        },
        // Admin surface colours
        surface: {
          50: "#f5f4f0",
          100: "#e8e6de",
          200: "#ccc9bc",
          300: "#a8a491",
          400: "#88836e",
          500: "#6e6952",
          600: "#56513f",
          700: "#3f3b2d",
          800: "#28261e",
          900: "#151410",
          950: "#0d0d0b",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
    },
  },
  plugins: [],
};
