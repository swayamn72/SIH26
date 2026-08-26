/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Console chrome — deep navy, used for the sidebar and headers.
        ink: {
          50: "#F1F5F9",
          100: "#E2E8F0",
          200: "#CBD5E1",
          300: "#94A3B8",
          400: "#64748B",
          500: "#475569",
          600: "#2A3F63",
          700: "#1E2E4A",
          800: "#16233A",
          900: "#0F1A2E",
          950: "#0A1220",
        },
        // Primary action colour.
        brand: {
          50: "#EFF6FF",
          100: "#DBEAFE",
          200: "#BFDBFE",
          300: "#93C5FD",
          400: "#60A5FA",
          500: "#3B82F6",
          600: "#2563EB",
          700: "#1D4ED8",
          800: "#1E40AF",
          900: "#1E3A8A",
        },
        // Risk semantics — one colour per tier, used everywhere a tier is shown.
        risk: {
          critical: "#DC2626",
          high: "#EA580C",
          medium: "#D97706",
          low: "#059669",
        },
      },
      fontFamily: {
        sans: [
          "Inter var",
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "Liberation Mono",
          "monospace",
        ],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.05), 0 1px 3px 0 rgb(15 23 42 / 0.04)",
        raised: "0 2px 4px -1px rgb(15 23 42 / 0.08), 0 4px 12px -2px rgb(15 23 42 / 0.06)",
        panel: "0 8px 24px -6px rgb(15 23 42 / 0.14)",
        inset: "inset 0 1px 0 0 rgb(255 255 255 / 0.06)",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-500px 0" },
          "100%": { backgroundPosition: "500px 0" },
        },
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "slide-down": {
          from: { opacity: "0", transform: "translateY(-6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.4s linear infinite",
        "fade-in": "fade-in 0.25s ease-out both",
        "slide-down": "slide-down 0.2s ease-out both",
      },
    },
  },
  plugins: [],
};
