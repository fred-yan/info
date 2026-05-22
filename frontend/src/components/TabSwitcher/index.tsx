import './TabSwitcher.css';

interface TabSwitcherProps {
  activeGroup: 'domestic' | 'international';
  onGroupChange: (group: 'domestic' | 'international') => void;
}

const tabs: { key: 'domestic' | 'international'; label: string }[] = [
  { key: 'domestic', label: '国内热点' },
  { key: 'international', label: '国际热点' },
];

export function TabSwitcher({ activeGroup, onGroupChange }: TabSwitcherProps) {
  return (
    <div className="tab-switcher" role="tablist" aria-label="热点分组切换">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          role="tab"
          aria-selected={activeGroup === tab.key}
          className={`tab-switcher__tab${activeGroup === tab.key ? ' tab-switcher__tab--active' : ''}`}
          onClick={() => onGroupChange(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export default TabSwitcher;
