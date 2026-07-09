/**
 * Landing Page — showcases the platform value proposition,
 * customer pain points, key metrics, and CTA to start triage.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { startTriage } from '@/services/api';
import { authService } from '@/services/auth';

export function Landing() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStartTriage = async () => {
    if (!authService.isAuthenticated()) {
      navigate('/auth');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { session_id } = await startTriage();
      navigate(`/triage/${session_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start triage');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="landing">
      {/* Hero Section */}
      <section className="hero">
        <div className="hero__badge">AI-Powered Digital Triage</div>
        <h1 className="hero__title">
          From 12-minute phone calls<br />to <span className="hero__highlight">3-minute AI triage</span>
        </h1>
        <p className="hero__subtitle">
          A 24/7 conversational AI system that assesses symptoms, scores urgency,
          routes to the right specialist, and books appointments — consistently,
          every time, without burning nurse-hours.
        </p>
        <button
          className="btn btn--primary btn--large hero__cta"
          onClick={handleStartTriage}
          disabled={loading}
        >
          {loading ? 'Starting...' : 'Start Triage Now'}
        </button>
        {error && <p className="error-message">{error}</p>}
      </section>

      {/* Key Metrics */}
      <section className="metrics">
        <div className="metrics__card">
          <span className="metrics__number">1,200+</span>
          <span className="metrics__label">Patient inquiries daily</span>
        </div>
        <div className="metrics__card">
          <span className="metrics__number">12–20 min</span>
          <span className="metrics__label">Current nurse triage time</span>
        </div>
        <div className="metrics__card metrics__card--highlight">
          <span className="metrics__number">&lt; 3 min</span>
          <span className="metrics__label">AI triage time</span>
        </div>
        <div className="metrics__card">
          <span className="metrics__number">15</span>
          <span className="metrics__label">Clinics on one queue</span>
        </div>
      </section>

      {/* The Problem */}
      <section className="problem-section">
        <h2 className="section-title">The Problem</h2>
        <p className="section-subtitle">
          Triage is the front door — and today it's a bottleneck, not a safety net
        </p>

        <div className="pain-cards">
          <div className="pain-card pain-card--risk">
            <div className="pain-card__icon">⚠️</div>
            <h3>Clinical Risk</h3>
            <p className="pain-card__title">Inconsistent urgency scoring</p>
            <p>The same symptoms can be scored differently by different staff — no shared, repeatable clinical logic.</p>
          </div>

          <div className="pain-card pain-card--gap">
            <div className="pain-card__icon">🌙</div>
            <h3>Coverage Gap</h3>
            <p className="pain-card__title">No after-hours triage</p>
            <p>Nights and weekends default patients to the ER or an answering service, neither of which assesses urgency.</p>
          </div>

          <div className="pain-card pain-card--ops">
            <div className="pain-card__icon">🔀</div>
            <h3>Operational Drag</h3>
            <p className="pain-card__title">Specialist misrouting</p>
            <p>Symptom-to-department mapping is judgment-based, driving avoidable rebookings and delayed care.</p>
          </div>

          <div className="pain-card pain-card--compliance">
            <div className="pain-card__icon">🔒</div>
            <h3>Compliance Exposure</h3>
            <p className="pain-card__title">PHI handled ad hoc</p>
            <p>Patient details move across phone, fax, and email with no consistent encryption, redaction, or consent trail.</p>
          </div>

          <div className="pain-card pain-card--burnout">
            <div className="pain-card__icon">😮‍💨</div>
            <h3>Staff Burnout</h3>
            <p className="pain-card__title">Nurses tied to intake calls</p>
            <p>Skilled clinical staff spend hours on repetitive questions instead of higher-acuity work.</p>
          </div>

          <div className="pain-card pain-card--experience">
            <div className="pain-card__icon">👁️</div>
            <h3>Patient Experience</h3>
            <p className="pain-card__title">No visibility once you hang up</p>
            <p>Patients wait blind — no status, no timeline, no record of what they reported.</p>
          </div>
        </div>
      </section>

      {/* Market Opportunity */}
      <section className="opportunity-section">
        <h2 className="section-title">Scale of the Opportunity</h2>
        <p className="section-subtitle">One network's phone queue hides massive inefficiency</p>

        <div className="opp-stats">
          <div className="opp-stat">
            <span className="opp-stat__number">~438K</span>
            <span className="opp-stat__label">Triage calls per year</span>
            <span className="opp-stat__detail">1,200/day × 365</span>
          </div>
          <div className="opp-stat">
            <span className="opp-stat__number">~117K</span>
            <span className="opp-stat__label">Nurse-hours per year</span>
            <span className="opp-stat__detail">Tied up in call triage alone</span>
          </div>
          <div className="opp-stat">
            <span className="opp-stat__number">24/7</span>
            <span className="opp-stat__label">Digital coverage</span>
            <span className="opp-stat__detail">No gaps, no answering service</span>
          </div>
        </div>

        <div className="opp-drivers">
          <div className="opp-driver">
            <strong>Clinical staffing shortages</strong> — every hour on repetitive intake is an hour not spent on care
          </div>
          <div className="opp-driver">
            <strong>Telehealth normalization</strong> — 24/7 digital access is expected; phone-only triage is now a gap
          </div>
          <div className="opp-driver">
            <strong>Multi-clinic consolidation</strong> — networks growing faster than triage can standardize
          </div>
        </div>
      </section>

      {/* CTA Bottom */}
      <section className="cta-bottom">
        <h2>Experience it yourself</h2>
        <p>Complete a triage assessment in under 3 minutes</p>
        <button
          className="btn btn--primary btn--large"
          onClick={handleStartTriage}
          disabled={loading}
        >
          Start Triage Now
        </button>
      </section>
    </div>
  );
}
