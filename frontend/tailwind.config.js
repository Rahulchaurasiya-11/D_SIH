/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        legal: {
              

          dark: "#14171C",     // 🖥️ Niche wala hissa (Main Screen Background)
          primary: "#1A1D24",  // 🗺️ Upar wala dark hissa (Top Header / Navbar)
          card: "#1E222A",     // 📦 Content ke Boxes / Cards ka Background
          border: "#2A303C",   // 🎛️ Patli border lines ka color
          slate: "#94A3B8", 


          // slate: "#94A3B8",    // Clean Light Slate text/subtitles ke liye
          // dark: "#14171C",     // Main Outer Background (Ultra dark slate)
          // card: "#1E222A",     // Pure Inside Content Boxes (Matte dark grey)
          // border: "#2A303C",   // Thin premium divider lines
          // primary: "#1A1D24",  // Deepest Dark Grey (Top bar header aur navigation ke liye)
          
          emerald: "#10B981",  // Emerald for Compliant / Success states
          amber: "#F59E0B",    // Amber for Warnings
          crimson: "#EF4444"   // Crimson for Violations



          // slate: "#1E293B",    // Clean Dark Slate text ke liye
          // dark: "#F4F6F9",     // Aur thoda behter slate-white background
          // card: "#FFFFFF",     // Crisp pure white containers
          // border: "#E2E8F0",   // Clear modern thin borders
          // primary: "#0A2540",  // Deep Authoritative Navy Blue (Header & primary buttons)
          // emerald: "#10B981",  // System status indicators
          // amber: "#F59E0B",    // Warnings
          // crimson: "#EF4444"   // Violations


        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace']
      },
      animation: {
        'scan': 'scan 2.5s ease-in-out infinite',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate'
      },
      keyframes: {
        scan: {
          '0%, 100%': { top: '0%' },
          '50%': { top: '96%' }
        },
        glow: {
          '0%': { boxShadow: '0 0 15px rgba(59, 130, 246, 0.3)' },
          '100%': { boxShadow: '0 0 25px rgba(59, 130, 246, 0.7)' }
        }
      }
    },
  },
  plugins: [],
}
