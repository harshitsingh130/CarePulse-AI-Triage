/**
 * Visual severity slider (1-10) shown when AI asks for pain rating.
 * Large touch targets (44px min) for accessibility.
 */

import { useState } from 'react';

interface SeveritySliderProps {
  onSelect: (value: number) => void;
}

export function SeveritySlider({ onSelect }: SeveritySliderProps) {
  const [selected, setSelected] = useState<number | null>(null);

  const handleSelect = (value: number) => {
    setSelected(value);
    onSelect(value);
  };

  const getColor = (value: number): string => {
    if (value <= 3) return 'var(--success)';
    if (value <= 6) return 'var(--warning)';
    return 'var(--error)';
  };

  return (
    <div className="severity-slider" role="group" aria-label="Pain severity scale 1 to 10">
      <div className="severity-slider__labels">
        <span>Barely noticeable</span>
        <span>Moderate</span>
        <span>Worst imaginable</span>
      </div>
      <div className="severity-slider__buttons">
        {Array.from({ length: 10 }, (_, i) => i + 1).map((value) => (
          <button
            key={value}
            type="button"
            className={`severity-slider__btn ${selected === value ? 'severity-slider__btn--selected' : ''}`}
            style={{ backgroundColor: selected === value ? getColor(value) : undefined }}
            onClick={() => handleSelect(value)}
            aria-label={`Severity ${value} out of 10`}
            aria-pressed={selected === value}
          >
            {value}
          </button>
        ))}
      </div>
    </div>
  );
}
