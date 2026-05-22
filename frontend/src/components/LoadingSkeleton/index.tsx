import styles from './LoadingSkeleton.module.css';

interface LoadingSkeletonProps {
  rows?: number;
}

export function LoadingSkeleton({ rows = 5 }: LoadingSkeletonProps) {
  return (
    <div className={styles.container} role="status" aria-label="加载中">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className={`${styles.bar} ${i % 3 === 0 ? styles.barShort : i % 3 === 1 ? styles.barLong : styles.barMedium}`} />
      ))}
    </div>
  );
}
