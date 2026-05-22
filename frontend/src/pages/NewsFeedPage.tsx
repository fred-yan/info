import { useState, useCallback, useMemo } from 'react';
import { FilterBar } from '../components/FilterBar';
import { ArticleFeedList } from '../components/ArticleFeedList';
import { Pagination } from '../components/Pagination';
import { useNewsFeed } from '../hooks/useNewsFeed';
import { usePlatforms } from '../hooks/usePlatforms';
import type { FeedFilters } from '../types';
import './NewsFeedPage.css';

export function NewsFeedPage() {
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([]);
  const [selectedSection, setSelectedSection] = useState<string | null>(null);
  const [page, setPage] = useState<number>(1);

  const filters: FeedFilters = useMemo(
    () => ({ platforms: selectedPlatforms, section: selectedSection }),
    [selectedPlatforms, selectedSection]
  );

  const { data, loading } = useNewsFeed(filters, page);
  const { data: platforms } = usePlatforms();

  const platformNames = useMemo(() => {
    if (!platforms) return [];
    return platforms.map((p) => p.name);
  }, [platforms]);

  const sections = useMemo(() => {
    if (!data?.articles) return [];
    const unique = new Set(data.articles.map((a) => a.section).filter(Boolean));
    return Array.from(unique).sort();
  }, [data?.articles]);

  const handlePlatformChange = useCallback((platforms: string[]) => {
    setSelectedPlatforms(platforms);
    setPage(1);
  }, []);

  const handleSectionChange = useCallback((section: string | null) => {
    setSelectedSection(section);
    setPage(1);
  }, []);

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  return (
    <div className="news-feed-page">
      <FilterBar
        platforms={platformNames}
        sections={sections}
        selectedPlatforms={selectedPlatforms}
        selectedSection={selectedSection}
        onPlatformChange={handlePlatformChange}
        onSectionChange={handleSectionChange}
      />
      <ArticleFeedList
        articles={data?.articles ?? []}
        loading={loading}
      />
      <Pagination
        page={page}
        hasNext={data?.has_next ?? false}
        onPageChange={handlePageChange}
      />
    </div>
  );
}

export default NewsFeedPage;
