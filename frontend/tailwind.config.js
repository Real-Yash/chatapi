/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: { "2xl": "1200px" },
    },
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        border: "hsl(220 13% 91%)",
        background: "hsl(0 0% 100%)",
        foreground: "hsl(222 47% 11%)",
        muted: {
          DEFAULT: "hsl(220 14% 96%)",
          foreground: "hsl(220 9% 46%)",
        },
        accent: {
          DEFAULT: "hsl(160 84% 39%)",
          foreground: "hsl(0 0% 100%)",
        },
      },
      borderRadius: {
        xl: "0.75rem",
        lg: "0.625rem",
        md: "0.5rem",
      },
    },
  },
  plugins: [],
};
