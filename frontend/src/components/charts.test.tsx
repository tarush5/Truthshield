import { render, screen } from '@testing-library/react';

import { AreaChart, BarChart, niceTicks } from '@/components/charts';

describe('niceTicks', () => {
  it('uses integer 1/2/5 steps that cover the maximum', () => {
    expect(niceTicks(0)).toEqual([0, 1]);
    expect(niceTicks(3)).toEqual([0, 1, 2, 3]);
    expect(niceTicks(7)).toEqual([0, 2, 4, 6, 8]);
    expect(niceTicks(42)).toEqual([0, 10, 20, 30, 40, 50]);
    for (const max of [1, 9, 13, 99, 250, 1234]) {
      const ticks = niceTicks(max);
      expect(ticks[ticks.length - 1]).toBeGreaterThanOrEqual(max);
      expect(ticks.length).toBeLessThanOrEqual(6);
      expect(ticks.every(Number.isInteger)).toBe(true);
    }
  });
});

describe('charts', () => {
  it('expose their data as an accessible table', () => {
    render(
      <AreaChart
        label="Per day"
        xKey="date"
        data={[{ date: '2026-09-30', total: 4, high: 1 }, { date: '2026-10-01', total: 6, high: 2 }]}
        series={[{ key: 'total', label: 'All', color: '#fff', fill: true }, { key: 'high', label: 'High', color: '#f00' }]}
      />,
    );
    const table = screen.getByRole('table', { name: 'Per day' });
    expect(table).toHaveTextContent('2026-10-01');
    expect(table).toHaveTextContent('6');
  });

  it('renders bar values in the table', () => {
    render(<BarChart label="By level" data={[{ label: 'Low', value: 3, color: '#0f0' }, { label: 'Critical', value: 1, color: '#f00' }]} />);
    expect(screen.getByRole('rowheader', { name: 'Critical' }).nextSibling).toHaveTextContent('1');
  });
});
