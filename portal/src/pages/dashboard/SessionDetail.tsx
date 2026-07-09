/**
 * Session Detail — full clinical view with SOAP note, symptoms, and override panel.
 */

import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';

interface SessionData {
  session_id: string;
  patient_id: string;
  status: string;
  urgency_level: string | null;
  started_at: string;
  completed_at: string | null;
  primary_complaint: string | null;
  structured_symptoms: Record<string, any>;
  urgency_result: Record<string, any>;
  routing_decision: Record<string, any>;
  soap_note: string;
  patient_summary: Record<string, any> | null;
  conversation_history: Array<{ role: string; content: string }>;
  nurse_override: Record<string, any> | null;
}

interface AppointmentData {
  appointmentId: string;
  patientId: string;
  sessionId: string;
  department: string;
  specialistName?: string;
  clinicId: string;
  clinicName?: string;
  scheduledAt: string;
  status: string;
  durationMinutes?: number;
  bookedAt?: string;
  bookedBy?: string;
}

const URGENCY_OPTIONS = ['EMERGENCY', 'URGENT', 'STANDARD', 'ROUTINE'];
const URGENCY_COLORS: Record<string, string> = {
  EMERGENCY: '#dc2626',
  URGENT: '#b45309',
  STANDARD: '#2563eb',
  ROUTINE: '#15803d',
};

export function SessionDetail() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [session, setSession] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Override form state
  const [overrideUrgency, setOverrideUrgency] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [overrideLoading, setOverrideLoading] = useState(false);
  const [overrideSuccess, setOverrideSuccess] = useState<string | null>(null);

  // Appointments for overridden cases
  const [appointments, setAppointments] = useState<AppointmentData[]>([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);

  useEffect(() => {
    async function fetchSession() {
      try {
        const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
        const token = sessionStorage.getItem('accessToken');
        const res = await fetch(`${API_BASE}/admin/sessions/${sessionId}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          setSession(data);
          setOverrideUrgency(data.urgency_level || '');
        } else {
          setError('Session not found');
        }
      } catch (e) {
        setError('Failed to load session');
      } finally {
        setLoading(false);
      }
    }
    if (sessionId) fetchSession();
  }, [sessionId]);

  // Fetch appointments when session has an override
  useEffect(() => {
    async function fetchAppointments() {
      if (!session?.nurse_override || !session.patient_id) return;
      setAppointmentsLoading(true);
      try {
        const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
        const token = sessionStorage.getItem('accessToken');
        const res = await fetch(`${API_BASE}/admin/sessions/${sessionId}/appointments`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          setAppointments(data);
        }
      } catch (e) {
        console.error('Failed to load appointments for session', e);
      } finally {
        setAppointmentsLoading(false);
      }
    }
    fetchAppointments();
  }, [session?.nurse_override, session?.patient_id, sessionId]);

  const handleOverride = async () => {
    if (!overrideUrgency || !overrideReason.trim()) return;
    setOverrideLoading(true);
    setOverrideSuccess(null);
    try {
      const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
      const token = sessionStorage.getItem('accessToken');
      const res = await fetch(`${API_BASE}/admin/override`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          session_id: sessionId,
          urgency_level: overrideUrgency,
          reason: overrideReason,
        }),
      });
      if (res.ok) {
        const result = await res.json();
        setOverrideSuccess(`Urgency changed: ${result.original} → ${result.new}. Actions: ${(result.actions_taken || []).join(', ') || 'none'}`);
        setSession(prev => prev ? { ...prev, urgency_level: overrideUrgency, status: result.status || prev.status } : prev);
        setOverrideReason('');
      }
    } catch (e) {
      setError('Override failed');
    } finally {
      setOverrideLoading(false);
    }
  };

  if (loading) {
    return <div className="dash__page"><div className="skeleton skeleton--card" /><div className="skeleton skeleton--card" /></div>;
  }

  if (error || !session) {
    return (
      <div className="dash__page">
        <p className="error-message">{error || 'Session not found'}</p>
        <Link to="/dashboard" className="btn btn--secondary">← Back to Queue</Link>
      </div>
    );
  }

  const symptoms = session.structured_symptoms || {};

  return (
    <div className="dash__page">
      <div className="dash__page-header">
        <Link to="/dashboard" className="dash__back-link">← Back to Queue</Link>
        <h1 className="dash__title">Session Detail</h1>
        <span className="dash__subtitle">{session.primary_complaint || 'No complaint recorded'}</span>
      </div>

      <div className="dash__detail-grid">
        {/* Left column: clinical data */}
        <div className="dash__detail-main">
          {/* Urgency & Routing */}
          <section className="dash__card">
            <h2>Assessment</h2>
            <div className="dash__field-row">
              <div className="dash__field">
                <span className="dash__field-label">Urgency</span>
                <span className="dash__field-value" style={{ color: URGENCY_COLORS[session.urgency_level || ''] }}>
                  {session.urgency_level || 'Not scored'}
                </span>
              </div>
              <div className="dash__field">
                <span className="dash__field-label">Confidence</span>
                <span className="dash__field-value">
                  {session.urgency_result?.confidence ? `${(session.urgency_result.confidence * 100).toFixed(0)}%` : '—'}
                </span>
              </div>
              <div className="dash__field">
                <span className="dash__field-label">Department</span>
                <span className="dash__field-value">{session.routing_decision?.department || '—'}</span>
              </div>
              <div className="dash__field">
                <span className="dash__field-label">Status</span>
                <span className="dash__field-value">{session.status?.replace(/_/g, ' ')}</span>
              </div>
            </div>
            {session.urgency_result?.reasoning && (
              <div className="dash__reasoning">
                <span className="dash__field-label">AI Reasoning</span>
                <p>{session.urgency_result.reasoning}</p>
              </div>
            )}
          </section>

          {/* Structured Symptoms */}
          <section className="dash__card">
            <h2>Structured Symptoms</h2>
            <div className="dash__field-row">
              <div className="dash__field">
                <span className="dash__field-label">Primary Complaint</span>
                <span className="dash__field-value">{symptoms.primary_complaint || session.primary_complaint || '—'}</span>
              </div>
              <div className="dash__field">
                <span className="dash__field-label">Severity</span>
                <span className="dash__field-value">{symptoms.severity || '—'}/10</span>
              </div>
              <div className="dash__field">
                <span className="dash__field-label">Onset</span>
                <span className="dash__field-value">{symptoms.onset || '—'}</span>
              </div>
              <div className="dash__field">
                <span className="dash__field-label">Duration</span>
                <span className="dash__field-value">{symptoms.duration_pattern || '—'}</span>
              </div>
            </div>
            {symptoms.associated_symptoms && symptoms.associated_symptoms.length > 0 && (
              <div className="dash__reasoning">
                <span className="dash__field-label">Associated Symptoms</span>
                <p>{symptoms.associated_symptoms.join(', ')}</p>
              </div>
            )}
            {symptoms.medications && symptoms.medications.length > 0 && (
              <div className="dash__reasoning">
                <span className="dash__field-label">Medications</span>
                <p>{symptoms.medications.join(', ')}</p>
              </div>
            )}
          </section>

          {/* SOAP Note */}
          {session.soap_note && (
            <section className="dash__card">
              <h2>SOAP Note</h2>
              <pre className="dash__soap">{session.soap_note}</pre>
            </section>
          )}

          {/* Conversation History */}
          {session.conversation_history && session.conversation_history.length > 0 && (
            <section className="dash__card">
              <h2>Conversation ({session.conversation_history.length} messages)</h2>
              <div className="dash__conversation">
                {session.conversation_history.map((msg, i) => (
                  <div key={i} className={`dash__msg dash__msg--${msg.role}`}>
                    <span className="dash__msg-role">{msg.role === 'patient' ? 'Patient' : 'AI'}</span>
                    <p>{msg.content}</p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Right column: override panel */}
        <div className="dash__detail-aside">
          <section className="dash__card dash__card--override">
            <h2>Override Urgency</h2>
            {session.nurse_override && (
              <div className="dash__override-existing">
                <span className="dash__field-label">Previous Override</span>
                <p>{session.nurse_override.original_urgency} → {session.nurse_override.override_urgency}</p>
                <p className="dash__override-reason">Reason: {session.nurse_override.reason}</p>
              </div>
            )}
            <div className="dash__override-form">
              <label className="dash__field-label">New Urgency Level</label>
              <div className="dash__urgency-options">
                {URGENCY_OPTIONS.map((opt) => (
                  <button
                    key={opt}
                    className={`dash__urgency-btn ${overrideUrgency === opt ? 'dash__urgency-btn--active' : ''}`}
                    style={{ '--urg-color': URGENCY_COLORS[opt] } as React.CSSProperties}
                    onClick={() => setOverrideUrgency(opt)}
                  >
                    {opt}
                  </button>
                ))}
              </div>
              <label className="dash__field-label">Reason for Override</label>
              <textarea
                className="dash__override-textarea"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="Clinical justification for changing the urgency level..."
                rows={3}
              />
              <button
                className="btn btn--primary btn--full"
                onClick={handleOverride}
                disabled={overrideLoading || !overrideReason.trim() || overrideUrgency === session.urgency_level}
              >
                {overrideLoading ? 'Submitting...' : 'Submit Override'}
              </button>
              {overrideSuccess && <p className="dash__override-success">{overrideSuccess}</p>}
            </div>
          </section>

          {/* Appointments associated with this overridden case */}
          {session.nurse_override && (
            <section className="dash__card">
              <h2>Associated Appointments</h2>
              {appointmentsLoading ? (
                <div className="skeleton skeleton--card" style={{ height: '60px' }} />
              ) : appointments.length > 0 ? (
                <div className="dash__appointments-list">
                  {appointments.map((appt) => (
                    <div key={appt.appointmentId} className="dash__appointment-item">
                      <div className="dash__appointment-header">
                        <span className="dash__appointment-dept">{appt.department}</span>
                        <span className={`dash__status-pill dash__status-pill--${appt.status.toLowerCase()}`}>
                          {appt.status}
                        </span>
                      </div>
                      {appt.specialistName && (
                        <p className="dash__appointment-specialist">Specialist: {appt.specialistName}</p>
                      )}
                      <p className="dash__appointment-time">
                        {new Date(appt.scheduledAt).toLocaleDateString()} at{' '}
                        {new Date(appt.scheduledAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        {appt.durationMinutes && ` (${appt.durationMinutes} min)`}
                      </p>
                      {appt.clinicName && (
                        <p className="dash__appointment-clinic">{appt.clinicName}</p>
                      )}
                      {appt.bookedBy && (
                        <p className="dash__appointment-booked">Booked by: {appt.bookedBy.replace('nurse-override:', '')}</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ color: '#64748b', fontSize: '0.875rem' }}>No appointments booked for this session yet.</p>
              )}
            </section>
          )}

          {/* Session metadata */}
          <section className="dash__card">
            <h2>Session Info</h2>
            <div className="dash__meta">
              <div><span className="dash__field-label">Session ID</span><code>{session.session_id.slice(0, 8)}...</code></div>
              <div><span className="dash__field-label">Patient ID</span><code>{session.patient_id.slice(0, 8)}...</code></div>
              <div><span className="dash__field-label">Started</span><span>{new Date(session.started_at).toLocaleString()}</span></div>
              {session.completed_at && <div><span className="dash__field-label">Completed</span><span>{new Date(session.completed_at).toLocaleString()}</span></div>}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
