import type { ReactNode } from "react";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="light">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Sunlight</title>
        <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries,typography"></script>
        <link href="https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;600;700&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
        <script dangerouslySetInnerHTML={{
          __html: `
        tailwind.config = {
          darkMode: "class",
          theme: {
            extend: {
              "colors": {
                      "secondary-fixed": "#e5e2db",
                      "on-secondary-fixed-variant": "#474742",
                      "surface-tint": "#46636b",
                      "on-primary-fixed-variant": "#2e4b52",
                      "on-tertiary": "#ffffff",
                      "on-surface-variant": "#41484a",
                      "background": "#faf9f7",
                      "on-error": "#ffffff",
                      "secondary-container": "#e5e2db",
                      "inverse-on-surface": "#f1f1ef",
                      "primary-fixed-dim": "#adccd5",
                      "tertiary-fixed": "#cae6ff",
                      "on-tertiary-fixed": "#001e30",
                      "surface-dim": "#dadad8",
                      "on-primary-container": "#77949c",
                      "on-tertiary-fixed-variant": "#1a4b69",
                      "on-secondary-fixed": "#1c1c18",
                      "secondary-fixed-dim": "#c9c6c0",
                      "tertiary-container": "#002b42",
                      "surface-container": "#efeeec",
                      "surface": "#faf9f7",
                      "error": "#ba1a1a",
                      "on-error-container": "#93000a",
                      "surface-bright": "#faf9f7",
                      "on-primary": "#ffffff",
                      "surface-container-low": "#f4f3f1",
                      "on-secondary-container": "#65645f",
                      "secondary": "#5f5e59",
                      "outline": "#72787a",
                      "primary": "#00171c",
                      "on-secondary": "#ffffff",
                      "tertiary-fixed-dim": "#a0ccf0",
                      "inverse-primary": "#adccd5",
                      "on-surface": "#1a1c1b",
                      "inverse-surface": "#2f3130",
                      "primary-fixed": "#c9e8f1",
                      "primary-container": "#0d2c33",
                      "on-background": "#1a1c1b",
                      "tertiary": "#001524",
                      "on-tertiary-container": "#6994b6",
                      "on-primary-fixed": "#001f26",
                      "outline-variant": "#c1c7ca",
                      "surface-container-highest": "#e3e2e0",
                      "surface-container-lowest": "#ffffff",
                      "surface-variant": "#e3e2e0",
                      "error-container": "#ffdad6",
                      "surface-container-high": "#e9e8e6"
              },
              "borderRadius": {
                      "DEFAULT": "0.25rem",
                      "lg": "0.5rem",
                      "xl": "0.75rem",
                      "full": "9999px"
              },
              "spacing": {
                      "gutter": "24px",
                      "margin-desktop": "48px",
                      "margin-mobile": "16px",
                      "unit": "4px",
                      "max-width": "1280px"
              },
              "fontFamily": {
                      "display": [
                              "Fira Sans"
                      ],
                      "label-mono": [
                              "JetBrains Mono"
                      ],
                      "headline-lg": [
                              "Fira Sans"
                      ],
                      "body-lg": [
                              "Fira Sans"
                      ],
                      "body-md": [
                              "Fira Sans"
                      ],
                      "label-caps": [
                              "Fira Sans"
                      ],
                      "headline-md": [
                              "Fira Sans"
                      ]
              },
              "fontSize": {
                      "display": [
                              "44px",
                              {
                                      "lineHeight": "52px",
                                      "letterSpacing": "-0.02em",
                                      "fontWeight": "700"
                              }
                      ],
                      "label-mono": [
                              "14px",
                              {
                                      "lineHeight": "20px",
                                      "letterSpacing": "0.02em",
                                      "fontWeight": "500"
                              }
                      ],
                      "headline-lg": [
                              "32px",
                              {
                                      "lineHeight": "40px",
                                      "letterSpacing": "-0.01em",
                                      "fontWeight": "600"
                              }
                      ],
                      "body-lg": [
                              "18px",
                              {
                                      "lineHeight": "28px",
                                      "fontWeight": "400"
                              }
                      ],
                      "body-md": [
                              "16px",
                              {
                                      "lineHeight": "24px",
                                      "fontWeight": "400"
                              }
                      ],
                      "label-caps": [
                              "12px",
                              {
                                      "lineHeight": "16px",
                                      "letterSpacing": "0.05em",
                                      "fontWeight": "700"
                              }
                      ],
                      "headline-md": [
                              "24px",
                              {
                                      "lineHeight": "32px",
                                      "fontWeight": "600"
                              }
                      ]
              }
      },
          },
        }
          `
        }} />
      </head>
      <body className="bg-background text-on-background font-body-md antialiased min-h-screen flex flex-col">
        <nav className="bg-surface w-full border-b border-outline-variant flat no shadows transition-all duration-200 ease-in-out">
<div className="flex justify-between items-center px-margin-desktop py-4 max-w-max-width mx-auto">
<a href="/" className="font-display text-headline-md font-bold tracking-tight text-primary">
                SUNLIGHT PROJECT
            </a>
<div className="hidden md:flex space-x-8 font-body-md text-body-md">
<a className="text-on-surface-variant font-medium hover:text-primary hover:bg-surface-container-low transition-colors px-2 py-1" href="/#about">About</a>
<a className="text-on-surface-variant font-medium hover:text-primary hover:bg-surface-container-low transition-colors px-2 py-1" href="/#projects">Projects</a>
<a className="text-on-surface-variant font-medium hover:text-primary hover:bg-surface-container-low transition-colors px-2 py-1" href="/#principles">Principles</a>
<a className="text-on-surface-variant font-medium hover:text-primary hover:bg-surface-container-low transition-colors px-2 py-1" href="/#support">Support</a>
<a className="text-on-surface-variant font-medium hover:text-primary hover:bg-surface-container-low transition-colors px-2 py-1" href="/#contact">Contact</a>
</div>
<div className="flex items-center space-x-4">
<button className="text-on-surface-variant hover:text-primary">
<span className="material-symbols-outlined">search</span>
</button>
<button className="hidden md:inline-flex bg-primary text-on-primary font-body-md text-body-md px-6 py-2 border border-primary hover:bg-surface hover:text-primary transition-colors">
                    Support Us
                </button>
<button className="md:hidden text-on-surface-variant">
<span className="material-symbols-outlined">menu</span>
</button>
</div>
</div>
</nav>
        {children}
        <footer className="bg-surface-container w-full border-t border-outline-variant flat no shadows transition-opacity duration-150">
<div className="flex flex-col md:flex-row justify-between items-start md:items-center px-margin-desktop py-12 max-w-max-width mx-auto gap-gutter">
<div className="mb-8 md:mb-0">
<div className="font-display text-headline-sm font-semibold text-primary mb-2">
                    SUNLIGHT PROJECT
                </div>
<div className="font-label-mono text-label-mono text-on-surface-variant max-w-sm">
                    © 2026 The Sunlight Project. Independent public-interest project. Data integrity assured.
                </div>
</div>
<div className="flex flex-wrap gap-x-6 gap-y-2 font-label-mono text-label-mono">
<a className="text-on-surface-variant hover:text-on-surface underline transition-opacity" href="/legal">Legal</a>
<a className="text-on-surface-variant hover:text-on-surface underline transition-opacity" href="/privacy">Privacy Policy</a>
<a className="text-on-surface-variant hover:text-on-surface underline transition-opacity" href="/accessibility">Accessibility</a>
<a className="text-on-surface-variant hover:text-on-surface underline transition-opacity" href="/contact">Contact</a>
<a className="text-on-surface-variant hover:text-on-surface underline transition-opacity" href="/archives">Archives</a>
</div>
</div>
</footer>
      </body>
    </html>
  );
}
