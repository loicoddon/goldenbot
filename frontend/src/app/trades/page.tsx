import { TradesTable } from '@/components/TradesTable';

export default function TradesPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Trade history</h1>
      <TradesTable limit={200} />
    </div>
  );
}
