import type { KeywordItemProps } from '../../types';
import { formatScore, formatCoverage } from '../../utils/transformations';
import './KeywordItem.css';

function getTrendIndicator(direction?: 'rising' | 'falling' | 'stable'): string {
  switch (direction) {
    case 'rising':
      return '↑';
    case 'falling':
      return '↓';
    case 'stable':
    default:
      return '—';
  }
}

function getTrendLabel(direction?: 'rising' | 'falling' | 'stable'): string {
  switch (direction) {
    case 'rising':
      return '上升';
    case 'falling':
      return '下降';
    case 'stable':
    default:
      return '持平';
  }
}

export function KeywordItem({ data, isSelected, onClick }: KeywordItemProps) {
  const trendIndicator = getTrendIndicator(data.trend_direction);
  const trendLabel = getTrendLabel(data.trend_direction);
  const trendClass = `keyword-item__trend keyword-item__trend--${data.trend_direction || 'stable'}`;

  return (
    <button
      className={`keyword-item${isSelected ? ' keyword-item--selected' : ''}`}
      onClick={() => onClick(data.keyword)}
      aria-pressed={isSelected}
      aria-label={`关键词: ${data.keyword}, 排名 ${data.rank}, 分数 ${formatScore(data.score)}, 覆盖率 ${formatCoverage(data.coverage)}, 趋势 ${trendLabel}`}
    >
      <span className="keyword-item__rank">{data.rank}</span>
      <span className="keyword-item__keyword">{data.keyword}</span>
      <span className="keyword-item__score">{formatScore(data.score)}</span>
      <span className="keyword-item__coverage">{formatCoverage(data.coverage)}</span>
      <span className={trendClass} aria-label={trendLabel}>
        {trendIndicator}
      </span>
    </button>
  );
}

export default KeywordItem;
