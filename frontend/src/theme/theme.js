export const theme = {
  colors: {
    bg: '#0f1117',
    surface: '#1a1d27',
    surfaceHover: '#242836',
    border: '#2a2e3a',
    text: '#e1e4eb',
    textMuted: '#8b8fa3',
    accent: '#5b7ff5',
    accentHover: '#4a6de0',
    score: {
      high: '#4ade80',   // green, score >= 8
      mid: '#fbbf24',    // yellow, score >= 6
      low: '#f87171',    // red, score < 6
    },
    status: {
      new: '#5b7ff5',
      queued: '#a78bfa',
      filming_today: '#f59e0b',
      filmed: '#4ade80',
      captioned: '#2dd4bf',
      posted: '#34d399',
      archived: '#6b7280',
    },
    filmingPriority: {
      film_now: '#ef4444',
      film_soon: '#f97316',
      batch_next: '#3b82f6',
      shelved: '#6b7280',
    },
    overlay: 'rgba(0, 0, 0, 0.5)',
  },
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    xxl: '48px',
  },
  radius: {
    sm: '6px',
    md: '10px',
    lg: '16px',
  },
  shadows: {
    card: '0 2px 8px rgba(0, 0, 0, 0.3)',
    panel: '-4px 0 24px rgba(0, 0, 0, 0.5)',
  },
  fonts: {
    body: "'Inter', -apple-system, sans-serif",
    mono: "'JetBrains Mono', monospace",
  },
  fontSize: {
    xs: '12px',
    sm: '14px',
    md: '16px',
    lg: '20px',
    xl: '28px',
    score: '36px',
  },
}
