/**
 * Theme color switcher — one-click theme change.
 * Persists selection to localStorage.
 */

import { useEffect, useState } from 'react';

const THEMES = [
  { id: 'rose', label: 'Rose', color: '#e11d48' },
  { id: 'blue', label: 'Blue', color: '#2563eb' },
  { id: 'teal', label: 'Teal', color: '#0d9488' },
  { id: 'purple', label: 'Purple', color: '#9333ea' },
] as const;

type ThemeId = (typeof THEMES)[number]['id'];

export function ThemeSwitcher() {
  const [active, setActive] = useState<ThemeId>(() => {
    return (localStorage.getItem('theme') as ThemeId) || 'rose';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', active);
    localStorage.setItem('theme', active);
  }, [active]);

  // Load saved theme on mount
  useEffect(() => {
    const saved = localStorage.getItem('theme') as ThemeId;
    if (saved) {
      document.documentElement.setAttribute('data-theme', saved);
      setActive(saved);
    }
  }, []);

  return (
    <div className="theme-switcher" aria-label="Choose theme color">
      {THEMES.map((theme) => (
        <button
          key={theme.id}
          className={`theme-switcher__dot ${active === theme.id ? 'theme-switcher__dot--active' : ''}`}
          style={{ background: theme.color }}
          onClick={() => setActive(theme.id)}
          aria-label={`${theme.label} theme`}
          title={theme.label}
        />
      ))}
    </div>
  );
}
