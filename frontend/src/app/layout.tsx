import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'AI Digital Twin - Laptop Telemetry',
  description: 'AI-driven digital twin analysis and real-time visualization dashboard for laptop telemetry logs.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
