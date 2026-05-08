import type { ReactNode } from "react";
import "./styles.css";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-NZ">
      <head>
        <title>Sunlight</title>
        <meta
          name="description"
          content="Sunlight collects and preserves official information disclosure material for responsible public-interest reuse."
        />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
