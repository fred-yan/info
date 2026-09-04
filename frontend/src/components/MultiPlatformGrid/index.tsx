import { PlatformCardGroup } from '../PlatformCard';
import type { PlatformMetadata } from '../../types';
import styles from './MultiPlatformGrid.module.css';

interface MultiPlatformGridProps {
  platforms: PlatformMetadata[];
}

export function MultiPlatformGrid({ platforms }: MultiPlatformGridProps) {
  if (platforms.length === 0) return null;

  return (
    <div className={styles.grid}>
      {platforms.map((p) => (
        <PlatformCardGroup
          key={p.name}
          platform={p.name}
          label={p.label}
          updateInterval={p.update_interval}
        />
      ))}
    </div>
  );
}

export default MultiPlatformGrid;
