// ORBIT Frontend - Theme Hook
// Theme management with localStorage persistence and system preference detection

import { useEffect, useState } from 'react';

export type Theme = 'dark' | 'light';

export function useTheme(): { theme: Theme; resolvedTheme: Theme; setTheme: (theme: Theme) => void } {
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('orbit-theme') as Theme | null;
      if (stored) return stored;
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return 'dark';
  });

  const [resolvedTheme, setResolvedTheme] = useState<Theme>(theme);

  // Update resolved theme when theme changes
  useEffect(() => {
    setResolvedTheme(theme);
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('orbit-theme', theme);
  }, [theme]);

  // Listen for system theme changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e: MediaQueryListEvent) => {
      const stored = localStorage.getItem('orbit-theme');
      if (!stored) {
        const newTheme = e.matches ? 'dark' : 'light';
        setThemeState(newTheme);
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
  };

  return { theme, resolvedTheme, setTheme };
}