/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  darkMode: 'class',
  theme: {
    extend: {
      // ── Design tokens from DESIGN.md / code.html ──────────────────────
      colors: {
        'primary':                  '#006c4f',
        'on-primary':               '#ffffff',
        'primary-container':        '#00d09c',
        'on-primary-container':     '#00533c',
        'primary-fixed':            '#59fdc5',
        'primary-fixed-dim':        '#2fe0aa',
        'on-primary-fixed':         '#002116',
        'on-primary-fixed-variant': '#00513b',
        'inverse-primary':          '#2fe0aa',

        'secondary':                '#3247e2',
        'on-secondary':             '#ffffff',
        'secondary-container':      '#4f63fb',
        'on-secondary-container':   '#fffbff',
        'secondary-fixed':          '#dfe0ff',
        'secondary-fixed-dim':      '#bcc2ff',
        'on-secondary-fixed':       '#000b62',
        'on-secondary-fixed-variant': '#102bcd',

        'tertiary':                 '#565e74',
        'on-tertiary':              '#ffffff',
        'tertiary-container':       '#afb7d0',
        'on-tertiary-container':    '#40485d',
        'tertiary-fixed':           '#dae2fd',
        'tertiary-fixed-dim':       '#bec6e0',
        'on-tertiary-fixed':        '#131b2e',
        'on-tertiary-fixed-variant':'#3f465c',

        'error':                    '#ba1a1a',
        'on-error':                 '#ffffff',
        'error-container':          '#ffdad6',
        'on-error-container':       '#93000a',

        'surface':                  '#f7f9fb',
        'surface-dim':              '#d8dadc',
        'surface-bright':           '#f7f9fb',
        'surface-variant':          '#e0e3e5',
        'surface-tint':             '#006c4f',
        'surface-container-lowest': '#ffffff',
        'surface-container-low':    '#f2f4f6',
        'surface-container':        '#eceef0',
        'surface-container-high':   '#e6e8ea',
        'surface-container-highest':'#e0e3e5',

        'on-surface':               '#191c1e',
        'on-surface-variant':       '#3c4a43',
        'background':               '#f7f9fb',
        'on-background':            '#191c1e',
        'outline':                  '#6b7b72',
        'outline-variant':          '#bacac1',
        'inverse-surface':          '#2d3133',
        'inverse-on-surface':       '#eff1f3',
      },
      fontFamily: {
        headline: ['Manrope', 'sans-serif'],
        body:     ['Public Sans', 'sans-serif'],
        label:    ['Public Sans', 'sans-serif'],
      },
      borderRadius: {
        sm:  '0.25rem',
        DEFAULT: '0.25rem',
        md:  '0.5rem',
        lg:  '0.75rem',
        xl:  '0.75rem',
        '2xl': '1rem',
        full: '9999px',
      },
      animation: {
        'bounce-dot': 'bounceDot 1s infinite',
      },
      keyframes: {
        bounceDot: {
          '0%, 80%, 100%': { transform: 'translateY(0)' },
          '40%':           { transform: 'translateY(-6px)' },
        },
      },
    },
  },
  plugins: [],
};
