import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { EmptyState } from '../EmptyState';
import type { TrendChartProps } from '../../types';
import styles from './TrendChart.module.css';

function formatDate(timestamp: string): string {
  const date = new Date(timestamp);
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${month}-${day}`;
}

function formatTooltipTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function TrendChart({ data, keyword }: TrendChartProps) {
  if (data.length < 2) {
    return <EmptyState message="数据不足，无法显示趋势图" />;
  }

  const chartData = data.map((point) => ({
    ...point,
    dateLabel: formatDate(point.timestamp),
  }));

  return (
    <div className={styles.container}>
      <h3 className={styles.title}>「{keyword}」趋势</h3>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <XAxis dataKey="dateLabel" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload || payload.length === 0) return null;
              const point = payload[0].payload as (typeof chartData)[number];
              return (
                <div className={styles.tooltip}>
                  <p className={styles.tooltipTime}>{formatTooltipTime(point.timestamp)}</p>
                  <p className={styles.tooltipScore}>得分: {point.score.toFixed(2)}</p>
                </div>
              );
            }}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#4f7cff"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
