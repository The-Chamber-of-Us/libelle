import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        libelle: {
          indigo: "#4F46E5",
          violet: "#8B5CF6",
          slate: "#72727B",
          page: "#F8FAFF",
          hero: "#EEF2FF"
        }
      },
      fontFamily: {
        inter: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"]
      },
      boxShadow: {
        soft: "0px 14px 24px rgba(79, 70, 229, 0.05)",
        hero:
          "0px 3px 6px rgba(79,70,229,0.05), 0px 11px 11px rgba(79,70,229,0.04), 0px 25px 15px rgba(79,70,229,0.03), 0px 44px 18px rgba(79,70,229,0.01), 0px 69px 19px rgba(79,70,229,0)"
      }
    }
  },
  plugins: []
} satisfies Config;
