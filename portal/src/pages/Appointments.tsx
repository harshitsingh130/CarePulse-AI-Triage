/**
 * Appointments Page — shows upcoming appointments with reschedule capability.
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getAppointments, rescheduleAppointment } from '@/services/api';
import type { Appointment } from '@/types';

export function Appointments() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Reschedule state
  const [rescheduleId, setRescheduleId] = useState<string | null>(null);
  const [newDate, setNewDate] = useState('');
  const [newTime, setNewTime] = useState('');
  const [rescheduleLoading, setRescheduleLoading] = useState(false);
  const [rescheduleSuccess, setRescheduleSuccess] = useState<string | null>(null);
  const [rescheduleError, setRescheduleError] = useState<string | null>(null);

  const fetchAppointments = async () => {
    try {
      const data = await getAppointments();
      setAppointments(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load appointments');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAppointments();
  }, []);

  const handleReschedule = async (appointmentId: string) => {
    if (!newDate || !newTime) {
      setRescheduleError('Please select both a date and time');
      return;
    }

    const newDateTime = `${newDate}T${newTime}:00Z`;

    // Quick client-side check
    if (new Date(newDateTime) <= new Date()) {
      setRescheduleError('Please select a future date and time');
      return;
    }

    setRescheduleLoading(true);
    setRescheduleError(null);
    setRescheduleSuccess(null);

    try {
      const result = await rescheduleAppointment(appointmentId, newDateTime);
      setRescheduleSuccess(result.message);
      setRescheduleId(null);
      setNewDate('');
      setNewTime('');
      // Refresh appointments list
      fetchAppointments();
    } catch (e) {
      setRescheduleError(e instanceof Error ? e.message : 'Failed to reschedule');
    } finally {
      setRescheduleLoading(false);
    }
  };

  const openReschedule = (appt: Appointment) => {
    setRescheduleId(appt.appointmentId);
    setRescheduleError(null);
    setRescheduleSuccess(null);
    // Pre-fill with current date/time
    const dt = new Date(appt.scheduledAt);
    setNewDate(dt.toISOString().split('T')[0]);
    setNewTime(dt.toTimeString().slice(0, 5));
  };

  const cancelReschedule = () => {
    setRescheduleId(null);
    setNewDate('');
    setNewTime('');
    setRescheduleError(null);
  };

  // Get minimum date (tomorrow)
  const minDate = new Date(Date.now() + 86400000).toISOString().split('T')[0];

  if (loading) {
    return <div className="appointments-page"><div className="skeleton skeleton--card" /></div>;
  }

  if (error) {
    return <div className="appointments-page"><p className="error-message">{error}</p></div>;
  }

  return (
    <div className="appointments-page">
      <h1>My Appointments</h1>
      <p className="page-description">Upcoming specialist appointments scheduled from your triage assessments.</p>

      {/* Success toast */}
      {rescheduleSuccess && (
        <div className="appt-toast appt-toast--success" role="status">
          {rescheduleSuccess}
          <button className="appt-toast__close" onClick={() => setRescheduleSuccess(null)} aria-label="Dismiss">×</button>
        </div>
      )}

      {appointments.length === 0 ? (
        <div className="empty-state">
          <p>No upcoming appointments.</p>
          <p>Complete a triage to get matched and scheduled with the right specialist.</p>
          <Link to="/" className="btn btn--primary">Start Triage</Link>
        </div>
      ) : (
        <div className="appointments-list">
          {appointments.map((appt) => (
            <div key={appt.appointmentId} className="appointment-card">
              <div className="appointment-card__top">
                <div className="appointment-card__dept">{appt.department}</div>
                <span className={`appointment-card__status appointment-card__status--${appt.status.toLowerCase()}`}>
                  {appt.status}
                </span>
              </div>
              {appt.specialistName && (
                <p className="appointment-card__specialist">With: {appt.specialistName}</p>
              )}
              <p className="appointment-card__time">
                {new Date(appt.scheduledAt).toLocaleDateString()} at{' '}
                {new Date(appt.scheduledAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
              <p className="appointment-card__clinic">{appt.clinicName || appt.clinicId}</p>
              {appt.preparationNotes && (
                <p className="appointment-card__notes">{appt.preparationNotes}</p>
              )}

              {/* Reschedule section */}
              {(appt.status === 'SCHEDULED' || appt.status === 'CONFIRMED') && (
                <div className="appointment-card__actions">
                  {rescheduleId === appt.appointmentId ? (
                    <div className="appointment-card__reschedule-form">
                      <p className="appointment-card__reschedule-title">Reschedule Appointment</p>
                      <div className="appointment-card__reschedule-fields">
                        <div className="appointment-card__field">
                          <label htmlFor={`date-${appt.appointmentId}`}>New Date</label>
                          <input
                            id={`date-${appt.appointmentId}`}
                            type="date"
                            value={newDate}
                            min={minDate}
                            onChange={(e) => setNewDate(e.target.value)}
                            className="appointment-card__input"
                          />
                        </div>
                        <div className="appointment-card__field">
                          <label htmlFor={`time-${appt.appointmentId}`}>New Time</label>
                          <input
                            id={`time-${appt.appointmentId}`}
                            type="time"
                            value={newTime}
                            onChange={(e) => setNewTime(e.target.value)}
                            className="appointment-card__input"
                          />
                        </div>
                      </div>
                      {rescheduleError && (
                        <p className="appointment-card__error">{rescheduleError}</p>
                      )}
                      <div className="appointment-card__reschedule-actions">
                        <button
                          className="btn btn--primary btn--sm"
                          onClick={() => handleReschedule(appt.appointmentId)}
                          disabled={rescheduleLoading || !newDate || !newTime}
                        >
                          {rescheduleLoading ? 'Rescheduling...' : 'Confirm'}
                        </button>
                        <button
                          className="btn btn--secondary btn--sm"
                          onClick={cancelReschedule}
                          disabled={rescheduleLoading}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      className="btn btn--outline btn--sm"
                      onClick={() => openReschedule(appt)}
                    >
                      Reschedule
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
