import { createContext, useContext } from 'react';
import type { Theme, FontSize } from '../hooks/useSettings';

interface SettingsContextValue {
  theme:       Theme;
  setTheme:    (t: Theme)    => void;
  fontSize:    FontSize;
  setFontSize: (s: FontSize) => void;
}

export const SettingsContext = createContext<SettingsContextValue>({
  theme:       'auto',
  setTheme:    () => {},
  fontSize:    'medium',
  setFontSize: () => {},
});

export function useSettingsContext() {
  return useContext(SettingsContext);
}
