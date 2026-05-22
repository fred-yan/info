import { usePlatforms } from '../../hooks/usePlatforms';
import { isStale } from '../../utils/transformations';
import { LoadingSkeleton } from '../LoadingSkeleton';
import styles from './PlatformStatus.module.css';

export default function PlatformStatus() {
  const { data: platforms, loading, error } = usePlatforms();

  if (loading) {
    return (
      <div className={styles.container}>
        <h1 className={styles.title}>平台状态</h1>
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <h1 className={styles.title}>平台状态</h1>
        <div className={styles.error} role="alert">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!platforms || platforms.length === 0) {
    return (
      <div className={styles.container}>
        <h1 className={styles.title}>平台状态</h1>
        <p className={styles.empty}>暂无平台数据</p>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <h1 className={styles.title}>平台状态</h1>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>平台</th>
            <th>分组</th>
            <th>最后抓取时间</th>
            <th>文章数</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {platforms.map((platform) => {
            const stale = isStale(platform.last_fetch);
            return (
              <tr key={platform.name} className={stale ? styles.staleRow : ''}>
                <td className={styles.labelCell}>{platform.label}</td>
                <td>
                  <span className={platform.group === 'domestic' ? styles.groupDomestic : styles.groupInternational}>
                    {platform.group === 'domestic' ? '国内' : '国际'}
                  </span>
                </td>
                <td className={styles.timestampCell}>
                  {formatTimestamp(platform.last_fetch)}
                </td>
                <td className={styles.countCell}>{platform.article_count}</td>
                <td>
                  {stale ? (
                    <span className={styles.staleIndicator} title="数据可能过期">
                      <span className={styles.staleDot} aria-hidden="true" />
                      数据可能过期
                    </span>
                  ) : (
                    <span className={styles.freshIndicator}>正常</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return isoString;
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}
