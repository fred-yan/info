import { useState, useCallback } from 'react';
import { PlatformCardGroup } from '../PlatformCard';
import type { PlatformMetadata } from '../../types';
import styles from './MultiPlatformGrid.module.css';

type PlatformStatus = 'loading' | 'ok' | 'error' | 'empty';

interface MultiPlatformGridProps {
  platforms: PlatformMetadata[];
}

export function MultiPlatformGrid({ platforms }: MultiPlatformGridProps) {
  const [statusMap, setStatusMap] = useState<Record<string, PlatformStatus>>({});

  const handleStatusChange = useCallback((platform: string, status: PlatformStatus) => {
    setStatusMap((prev) => {
      if (prev[platform] === status) return prev; // no change → no re-render
      return { ...prev, [platform]: status };
    });
  }, []);

  if (platforms.length === 0) return null;

  // Split: platforms with data first, error/empty last
  // While still loading keep original order (status not yet known)
  const normalPlatforms: PlatformMetadata[] = [];
  const tailPlatforms: PlatformMetadata[] = [];

  for (const p of platforms) {
    const s = statusMap[p.name];
    if (s === 'error' || s === 'empty') {
      tailPlatforms.push(p);
    } else {
      normalPlatforms.push(p);
    }
  }

  const ordered = [...normalPlatforms, ...tailPlatforms];

  return (
    <div className={styles.grid}>
      {ordered.map((p) => (
        <PlatformCardGroup
          key={p.name}
          platform={p.name}
          label={p.label}
          updateInterval={p.update_interval}
          onStatusChange={handleStatusChange}
        />
      ))}
    </div>
  );
}

export default MultiPlatformGrid;
