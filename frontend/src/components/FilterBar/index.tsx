import type { FilterBarProps } from '../../types';
import './FilterBar.css';

export function FilterBar({
  platforms,
  sections,
  selectedPlatforms,
  selectedSection,
  onPlatformChange,
  onSectionChange,
}: FilterBarProps) {
  function handlePlatformToggle(platform: string) {
    if (selectedPlatforms.includes(platform)) {
      onPlatformChange(selectedPlatforms.filter((p) => p !== platform));
    } else {
      onPlatformChange([...selectedPlatforms, platform]);
    }
  }

  function handleSectionChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const value = e.target.value;
    onSectionChange(value === '' ? null : value);
  }

  return (
    <div className="filter-bar">
      <div className="filter-bar__group">
        <span className="filter-bar__label">全部平台</span>
        <div className="filter-bar__platforms" role="group" aria-label="平台筛选">
          {platforms.map((platform) => (
            <label key={platform} className="filter-bar__platform-option">
              <input
                type="checkbox"
                checked={selectedPlatforms.includes(platform)}
                onChange={() => handlePlatformToggle(platform)}
                aria-label={platform}
              />
              <span>{platform}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="filter-bar__group">
        <label className="filter-bar__label" htmlFor="section-filter">
          栏目
        </label>
        <select
          id="section-filter"
          className="filter-bar__section-select"
          value={selectedSection ?? ''}
          onChange={handleSectionChange}
        >
          <option value="">All</option>
          {sections.map((section) => (
            <option key={section} value={section}>
              {section}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export default FilterBar;
