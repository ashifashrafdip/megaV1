import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Automation Hub | Management Console',
  description: 'Enterprise Licensing, Device Security & Link Management',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0b0e14] text-[#e6edf3] antialiased">
        {children}
      </body>
    </html>
  );
}
