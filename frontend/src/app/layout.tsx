import './globals.css';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'GoldenBot — XAU/USD Virtual Trading',
  description: 'AI-powered virtual gold trading laboratory',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen flex flex-col">
          <header className="border-b border-bg-accent bg-bg-card/70 backdrop-blur sticky top-0 z-10">
            <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
              <Link href="/" className="flex items-center gap-2">
                <span className="text-2xl">🪙</span>
                <span className="font-bold text-lg">
                  <span className="text-gold">Golden</span>Bot
                </span>
                <span className="text-xs text-gray-400 ml-2">XAU/USD</span>
              </Link>
              <nav className="flex gap-6 text-sm">
                <Link href="/" className="hover:text-gold">Dashboard</Link>
                <Link href="/trades" className="hover:text-gold">Trades</Link>
                <Link href="/backtest" className="hover:text-gold">Backtest</Link>
                <Link href="/settings" className="hover:text-gold">Settings</Link>
              </nav>
            </div>
          </header>
          <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-6">{children}</main>
          <footer className="border-t border-bg-accent text-xs text-gray-500 py-3 text-center">
            GoldenBot v0.1.0 — 100% virtual · no real orders
          </footer>
        </div>
      </body>
    </html>
  );
}
