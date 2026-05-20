import './globals.css';
import type { Metadata, Viewport } from 'next';
import { Logo } from '@/components/Logo';
import { BottomNav, DesktopNav } from '@/components/Nav';

export const metadata: Metadata = {
  title: 'GoldenBot — XAU/USD Virtual Trading',
  description: 'AI-powered virtual gold trading laboratory',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#0B0F19',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen flex flex-col">
          <header className="border-b border-bg-accent bg-bg-card/70 backdrop-blur sticky top-0 z-10">
            <div className="max-w-7xl mx-auto px-4 md:px-6 py-2.5 md:py-3 flex items-center justify-between">
              <Logo />
              <DesktopNav />
            </div>
          </header>

          <main className="flex-1 max-w-7xl w-full mx-auto px-3 md:px-6 py-4 md:py-6 pb-24 md:pb-6">
            {children}
          </main>

          <footer className="border-t border-bg-accent text-[10px] md:text-xs text-gray-500 py-3 text-center pb-24 md:pb-3">
            GoldenBot v0.1.0 — 100% virtual · no real orders
          </footer>

          <BottomNav />
        </div>
      </body>
    </html>
  );
}
