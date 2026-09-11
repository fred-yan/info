import { useState, useRef, useEffect, useCallback } from 'react';
import { NavLink } from 'react-router-dom';
import { useSettingsContext } from '../../contexts/SettingsContext';
import type { Theme, FontSize } from '../../hooks/useSettings';
import styles from './NavBar.module.css';

// ── Settings panel ────────────────────────────────────────────────────────

function SettingsPanel({ onClose }: { onClose: () => void }) {
  const { theme, setTheme, fontSize, setFontSize } = useSettingsContext();

  const themes: { key: Theme; label: string; icon: string }[] = [
    { key: 'auto',  label: '跟随系统', icon: '🖥' },
    { key: 'light', label: '亮色',     icon: '☀️' },
    { key: 'dark',  label: '暗色',     icon: '🌙' },
  ];

  const fontSizes: { key: FontSize; label: string; desc: string }[] = [
    { key: 'small',  label: 'A-', desc: '小' },
    { key: 'medium', label: 'A',  desc: '中' },
    { key: 'large',  label: 'A+', desc: '大' },
  ];

  return (
    <div className={styles.settingsPanel} role="dialog" aria-label="显示设置">
      <div className={styles.settingsSection}>
        <span className={styles.settingsLabel}>字体大小</span>
        <div className={styles.settingsBtns}>
          {fontSizes.map(({ key, label, desc }) => (
            <button
              key={key}
              type="button"
              className={fontSize === key
                ? `${styles.settingsBtn} ${styles.settingsBtnActive}`
                : styles.settingsBtn}
              onClick={() => { setFontSize(key); }}
              aria-label={`字体${desc}`}
              aria-pressed={fontSize === key}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.settingsDivider} />

      <div className={styles.settingsSection}>
        <span className={styles.settingsLabel}>主题模式</span>
        <div className={styles.settingsBtns}>
          {themes.map(({ key, label, icon }) => (
            <button
              key={key}
              type="button"
              className={theme === key
                ? `${styles.settingsBtn} ${styles.settingsBtnActive}`
                : styles.settingsBtn}
              onClick={() => { setTheme(key); }}
              aria-label={label}
              aria-pressed={theme === key}
              title={label}
            >
              <span aria-hidden="true" style={{ fontSize: '1rem' }}>{icon}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── NavBar ────────────────────────────────────────────────────────────────

export default function NavBar() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  const handleToggle = useCallback(() => setSettingsOpen(v => !v), []);
  const handleClose = useCallback(() => setSettingsOpen(false), []);

  // Close on outside click
  useEffect(() => {
    if (!settingsOpen) return;
    function handleClick(e: MouseEvent) {
      if (
        panelRef.current && !panelRef.current.contains(e.target as Node) &&
        btnRef.current && !btnRef.current.contains(e.target as Node)
      ) {
        setSettingsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [settingsOpen]);

  // Close on Escape
  useEffect(() => {
    if (!settingsOpen) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setSettingsOpen(false);
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [settingsOpen]);

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
            热词榜
          </NavLink>
        </li>
        <li>
          <NavLink to="/platforms" className={({ isActive }) =>
            isActive ? `${styles.navLink} ${styles.active}` : styles.navLink}>
            平台状态
          </NavLink>
        </li>
      </ul>

      {/* Settings gear button */}
      <div className={styles.settingsWrapper}>
        <button
          ref={btnRef}
          type="button"
          className={settingsOpen
            ? `${styles.settingsGear} ${styles.settingsGearOpen}`
            : styles.settingsGear}
          onClick={handleToggle}
          aria-label="显示设置"
          aria-expanded={settingsOpen}
          aria-haspopup="dialog"
        >
          {/* Gear SVG */}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            aria-hidden="true">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>

        {settingsOpen && (
          <div ref={panelRef}>
            <SettingsPanel onClose={handleClose} />
          </div>
        )}
      </div>
    </nav>
  );
}
