import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const ThemeContext = createContext(null);
const STORAGE_KEY = 'lm.theme';

/** 'system' leaves the OS preference in charge; the other two are explicit choices. */
const MODES = ['light', 'dark', 'system'];

function readStored() {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return MODES.includes(value) ? value : 'system';
  } catch {
    return 'system';
  }
}

export function ThemeProvider({ children }) {
  const [mode, setMode] = useState(readStored);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('light', 'dark');
    if (mode !== 'system') root.classList.add(mode);

    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      /* private browsing - the class is still applied for this session */
    }
  }, [mode]);

  const resolved =
    mode === 'system'
      ? window.matchMedia?.('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      : mode;

  const cycle = useCallback(() => {
    setMode((current) => (current === 'light' ? 'dark' : current === 'dark' ? 'system' : 'light'));
  }, []);

  const value = useMemo(() => ({ mode, resolved, setMode, cycle }), [mode, resolved, cycle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used inside <ThemeProvider>');
  return context;
}
