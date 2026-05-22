import styles from './ErrorState.module.css';

interface ErrorStateProps {
  message: string;
  onRetry: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className={styles.container} role="alert">
      <p className={styles.message}>{message}</p>
      <button className={styles.retryButton} onClick={onRetry} type="button">
        重试
      </button>
    </div>
  );
}
