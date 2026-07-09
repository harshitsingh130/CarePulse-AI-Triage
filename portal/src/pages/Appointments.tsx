/**
 * Appointments Page — shows upcoming appointments.
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getAppointments } from '@/services/api';
import type { Appointment } from '@/types';

export function Appointments() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetch() {
      try {
        const data = await getAppointments();
        setAppointments(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load appointments');
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, []);

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
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
