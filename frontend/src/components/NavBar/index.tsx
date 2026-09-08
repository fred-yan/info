import { NavLink } from 'react-router-dom';
import { useSettingsContext } from '../../contexts/SettingsContext';
import type { Theme, FontSize } from '../../hooks/useSettings';
import styles from './NavBar.module.css';

// ── Theme icon ────────────────────────────────────────────────────────────

function ThemeIcon({ theme }: { theme: Theme }) {
  if (theme === 'light') return <span aria-hidden="true">☀️</span>;
  if (theme === 'dark')  return <span aria-hidden="true">🌙</span>;
  return <span aria-hidden="true" style={{ fontSize: '0.75rem' }}>自动</span>;
}

// ── NavBar ────────────────────────────────────────────────────────────────

export default function NavBar() {
  const { theme, setTheme, fontSize, setFontSize } = useSettingsContext();

  const nextTheme: Theme =
    theme === 'auto' ? 'light' : theme === 'light' ? 'dark' : 'auto';

  const themeLabel =
    theme === 'auto'  ? '跟随系统' :
    theme === 'light' ? '亮色模式' : '暗色模式';

  const fontSizes: { key: FontSize; label: string }[] = [
    { key: 'small',  label: 'A-' },
    { key: 'medium', label: 'A'  },
    { key: 'large',  label: 'A+' },
  ];

  return (
    <nav className={styles.navbar} aria-label="主导航">
      {/* Navigation links */}
      <ul className={styles.navList}>
        <li>
          <NavLink to="/" end className={({ isActive }) =>
            isActive ? `${styles.navLink} ${styles.active}` : styles.navLink}>
            热点快讯
          </NavLink>
        </li>
        <li>
          <NavLink to="/keywords" className={({ isActive }) =>
            isActive ? `${styles.navLink} ${styles.active}` : styles.navLink}>
            关键词榜
          </NavLink>
        </li>
        <li>
          <NavLink to="/platforms" className={({ isActive }) =>
            isActive ? `${styles.navLink} ${styles.active}` : styles.navLink}>
            平台状态
          </NavLink>
        </li>
      </ul>

      {/* Settings controls */}
      <div className={styles.controls} role="toolbar" aria-label="显示设置">
        {/* Font size: A- A A+ */}
        {fontSizes.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            className={fontSize === key
              ? `${styles.ctrlBtn} ${styles.ctrlBtnActive}`
              : styles.ctrlBtn}
            onClick={() => setFontSize(key)}
            aria-label={`字体${label === 'A-' ? '缩小' : label === 'A+' ? '放大' : '默认'}`}
            aria-pressed={fontSize === key}
          >
            {label}
          </button>
        ))}

        <span className={styles.separator} aria-hidden="true" />

        {/* Theme toggle */}
        <button
          type="button"
          className={styles.ctrlBtn}
          onClick={() => setTheme(nextTheme)}
          title={`当前: ${themeLabel}，点击切换`}
          aria-label={`切换主题，当前${themeLabel}`}
        >
          <ThemeIcon theme={theme} />
        </button>
      </div>
    </nav>
  );
}
