/**
 * Triage Status Page — shows results, progress, and next steps.
 */

import { Link, useParams } from 'react-router-dom';
import { UrgencyBadge } from '@/components/UrgencyBadge';
import { useTriageStatus } from '@/hooks/useTriageStatus';
import type { SessionStatus } from '@/types';

const PROGRESS_STEPS_DEFAULT = ['Assessment', 'Scoring', 'Routing', 'Appointment', 'Complete'];
const PROGRESS_STEPS_DONE = ['Assessment', 'Scoring', 'Routing', 'Appointment', 'Completed'];

function getStepIndex(status: SessionStatus): number {
  switch (status) {
    case 'IN_PROGRESS': return 0;
    case 'AWAITING_NURSE': return 1;
    case 'AWAITING_ROUTING': return 2;
    case 'SCHEDULED': return 3;
    case 'COMPLETED': return 4;
    case 'ESCALATED': return 1;
    default: return 0;
  }
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
}

function formatTime(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function Status() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { status, loading, error } = useTriageStatus(sessionId || null);

  if (loading) {
    return (
      <div className="status-page">
        <div className="skeleton skeleton--card" />
        <div className="skeleton skeleton--card" />
        <div className="skeleton skeleton--card" />
      </div>
    );
  }

  if (error || !status) {
    return (
      <div className="status-page">
        <h1>Triage Status</h1>
        <p className="error-message">Unable to load triage status. Please try again.</p>
        <Link to="/" className="btn btn--primary" style={{ marginTop: '24px' }}>Back to Home</Link>
      </div>
    );
  }

  const currentStep = getStepIndex(status.status);
  const isComplete = status.status === 'COMPLETED';
  const isEscalated = status.status === 'ESCALATED';

  return (
    <div className="status-page">
      <h1>Triage Status</h1>
      {status.primary_complaint && (
        <p className="page-description">Regarding: {status.primary_complaint}</p>
      )}

      {/* Progress Stepper */}
      <div className="progress-stepper" role="progressbar" aria-valuenow={currentStep} aria-valuemax={4}>
        {(isComplete ? PROGRESS_STEPS_DONE : PROGRESS_STEPS_DEFAULT).map((step, i) => {
          const isAllDone = status.status === 'COMPLETED';
          const stepComplete = isAllDone || i < currentStep;
          const stepActive = !isAllDone && i === currentStep;
          return (
            <div
              key={step}
              className={`progress-step ${stepComplete ? 'progress-step--complete' : ''} ${stepActive ? 'progress-step--active' : ''}`}
            >
              <div className="progress-step__dot">{stepComplete ? '✓' : i + 1}</div>
              <span className="progress-step__label">{step}</span>
            </div>
          );
        })}
      </div>

      {/* Escalation Alert */}
      {isEscalated && (
        <section className="status-card status-card--emergency" role="alert">
          <h2>⚠️ Emergency Escalation</h2>
          <p>Medical staff has been notified and will contact you shortly.</p>
          <p><strong>If symptoms worsen, call 911 immediately.</strong></p>
        </section>
      )}

      {/* Urgency Assessment */}
      {status.urgency_level && (
        <section className="status-card">
          <h2>Assessment Result</h2>
          <div className="status-card__row">
            <div className="status-card__field">
              <span className="status-card__label">Urgency Level</span>
              <UrgencyBadge level={status.urgency_level} />
            </div>
            {status.recommended_timeframe && (
              <div className="status-card__field">
                <span className="status-card__label">Recommended Timeframe</span>
                <span className="status-card__value">{status.recommended_timeframe}</span>
              </div>
            )}
            {status.department && (
              <div className="status-card__field">
                <span className="status-card__label">Department</span>
                <span className="status-card__value">{status.department}</span>
              </div>
            )}
          </div>
          {status.urgency_reasoning && (
            <div className="status-card__reasoning">
              <span className="status-card__label">Clinical Reasoning</span>
              <p>{status.urgency_reasoning}</p>
            </div>
          )}
        </section>
      )}

      {/* Patient Summary */}
      {status.patient_summary && (
        <section className="status-card">
          <h2>Your Summary</h2>
          <div className="status-card__summary">
            <div className="status-card__summary-item">
              <span className="status-card__label">Symptoms Reported</span>
              <p>{status.patient_summary.symptoms_reported}</p>
            </div>
            <div className="status-card__summary-item">
              <span className="status-card__label">Medications Reviewed</span>
              <p>{status.patient_summary.medications_reviewed}</p>
            </div>
            <div className="status-card__summary-item">
              <span className="status-card__label">Assessment</span>
              <p><strong>{status.patient_summary.urgency_level}</strong></p>
            </div>
            <div className="status-card__summary-item">
              <span className="status-card__label">Next Steps</span>
              <p>{status.patient_summary.next_steps}</p>
            </div>
          </div>
        </section>
      )}

      {/* Appointment */}
      {status.appointment && (
        <section className="status-card status-card--appointment">
          <h2>📅 Your Appointment</h2>
          <div className="status-card__row">
            <div className="status-card__field">
              <span className="status-card__label">Department</span>
              <span className="status-card__value">{status.appointment.department}</span>
            </div>
            {status.appointment.specialistName && (
              <div className="status-card__field">
                <span className="status-card__label">Specialist</span>
                <span className="status-card__value">{status.appointment.specialistName}</span>
              </div>
            )}
            <div className="status-card__field">
              <span className="status-card__label">Date & Time</span>
              <span className="status-card__value">
                {formatDate(status.appointment.scheduledAt)} at {formatTime(status.appointment.scheduledAt)}
              </span>
            </div>
          </div>
          {status.appointment.preparationNotes && (
            <div className="status-card__reasoning">
              <span className="status-card__label">Preparation Notes</span>
              <p>{status.appointment.preparationNotes}</p>
            </div>
          )}
        </section>
      )}

      {/* Session info */}
      <section className="status-card">
        <h2>Session Details</h2>
        <div className="status-card__row">
          <div className="status-card__field">
            <span className="status-card__label">Started</span>
            <span className="status-card__value">{formatDate(status.started_at)} at {formatTime(status.started_at)}</span>
          </div>
          {status.completed_at && (
            <div className="status-card__field">
              <span className="status-card__label">Completed</span>
              <span className="status-card__value">{formatDate(status.completed_at)} at {formatTime(status.completed_at)}</span>
            </div>
          )}
          <div className="status-card__field">
            <span className="status-card__label">Status</span>
            <span className="status-card__value">{isComplete ? 'Completed' : isEscalated ? 'Escalated' : 'In Progress'}</span>
          </div>
        </div>
      </section>

      {/* Actions */}
      <div className="status-page__actions">
        <Link to="/" className="btn btn--primary">Start New Triage</Link>
        <Link to="/history" className="btn btn--secondary">View History</Link>
      </div>
    </div>
  );
}
