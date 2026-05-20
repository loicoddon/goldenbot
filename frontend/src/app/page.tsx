import { NewsPanel } from '@/components/NewsPanel';
import { PortfolioCard } from '@/components/PortfolioCard';
import { PriceChart } from '@/components/PriceChart';
import { StatusBar } from '@/components/StatusBar';
import { TradesTable } from '@/components/TradesTable';

export default function DashboardPage() {
  return (
    <div className="space-y-4">
      <StatusBar />
      <PortfolioCard />
      <PriceChart />
      <NewsPanel />
      <TradesTable limit={20} />
    </div>
  );
}
