import './globals.css';
import type { Metadata, Viewport } from 'next';
import Link from 'next/link';
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
            <div className="max-w-7xl mx-auto px-4 md:px-6 py-3 md:py-4 flex items-center justify-between">
              <Link href="/" className="flex items-center gap-2 min-w-0">
                <span className="text-xl md:text-2xl">🪙</span>
                <span className="font-bold text-base md:text-lg truncate">
                  <span className="text-gold">Golden</span>Bot
                </span>
                <span className="text-[10px] md:text-xs text-gray-400 ml-1 md:ml-2 hidden sm:inline">
                  XAU/USD
                </span>
              </Link>
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
