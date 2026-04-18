import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'The Precision Ledger | Mutual Fund Assistant',
  description:
    'Facts-only mutual fund FAQ assistant. Access factual data, compliance rules, and fund specifics. No investment advice.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="light">
      <head>
        {/* Fonts: Manrope (headlines) + Public Sans (body) + Material Symbols (icons) */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=Public+Sans:wght@400;500;600&family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-surface text-on-surface min-h-screen">{children}</body>
    </html>
  );
}
