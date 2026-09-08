import { useState, useEffect, useCallback } from 'react';

export type Theme    = 'light' | 'dark' | 'auto';
export type FontSize = 'small' | 'medium' | 'large';

const STORAGE_THEME     = 'app-theme';
const STORAGE_FONT_SIZE = 'app-font-size';

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === 'auto') {
    root.removeAttribute('data-theme');
  } else {
    root.setAttribute('data-theme', theme);
  }
}

function applyFontSize(size: FontSize) {
  document.documentElement.setAttribute('data-font-size', size);
}

function readTheme(): Theme {
  const v = localStorage.getItem(STORAGE_THEME);
  return (v === 'light' || v === 'dark' || v === 'auto') ? v : 'auto';
}

function readFontSize(): FontSize {
  const v = localStorage.getItem(STORAGE_FONT_SIZE);
  return (v === 'small' || v === 'medium' || v === 'large') ? v : 'medium';
}

/**
 * Global settings: theme (light / dark / auto) and font size (small / medium / large).
 * Persists to localStorage and syncs to <html> data attributes immediately.
 */
export function useSettings() {
  const [theme,    setThemeState]    = useState<Theme>(readTheme);
  const [fontSize, setFontSizeState] = useState<FontSize>(readFontSize);

  // Apply on mount
  useEffect(() => {
    applyTheme(theme);
    applyFontSize(fontSize);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    localStorage.setItem(STORAGE_THEME, t);
    applyTheme(t);
  }, []);

  const setFontSize = useCallback((s: FontSize) => {
    setFontSizeState(s);
    localStorage.setItem(STORAGE_FONT_SIZE, s);
    applyFontSize(s);
  }, []);

  return { theme, setTheme, fontSize, setFontSize };
}
