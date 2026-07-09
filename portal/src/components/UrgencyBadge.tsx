/**
 * Color-coded urgency level badge.
 * Uses colored text on light background for readability.
 */

import type { UrgencyLevel } from '@/types';

interface UrgencyBadgeProps {
  level: UrgencyLevel;
}

const URGENCY_STYLES: Record<UrgencyLevel, { color: string; label: string }> = {
  EMERGENCY: { color: 'var(--error-600)', label: 'Emergency' },
  URGENT: { color: 'var(--warning-700)', label: 'Urgent' },
  STANDARD: { color: '#2563eb', label: 'Standard' },
  ROUTINE: { color: 'var(--success-700)', label: 'Routine' },
};

export function UrgencyBadge({ level }: UrgencyBadgeProps) {
  const style = URGENCY_STYLES[level];

  return (
    <span
      className="urgency-badge"
      style={{ color: style.color }}
      aria-label={`Urgency level: ${style.label}`}
    >
      {style.label}
    </span>
  );
}
