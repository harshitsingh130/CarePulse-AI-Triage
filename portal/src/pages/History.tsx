/**
 * Triage History Page — shows past triage sessions.
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getTriageHistory } from '@/services/api';
import { UrgencyBadge } from '@/components/UrgencyBadge';
import type { TriageHistoryItem } from '@/types';

export function History() {
  const [history, setHistory] = useState<TriageHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetch() {
      try {
        const data = await getTriageHistory();
        setHistory(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load history');
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, []);

  if (loading) {
    return <div className="history-page"><div className="skeleton skeleton--card" /><div className="skeleton skeleton--card" /></div>;
  }

  if (error) {
    return <div className="history-page"><p className="error-message">{error}</p></div>;
  }

  return (
    <div className="history-page">
      <h1>Triage History</h1>
      <p className="page-description">Review your past triage sessions and follow up on any assessments.</p>

      {history.length === 0 ? (
        <div className="empty-state">
          <p>No triage sessions yet.</p>
          <p>Start a triage to get an instant AI-powered health assessment.</p>
          <Link to="/" className="btn btn--primary">Start Your First Triage</Link>
        </div>
      ) : (
        <div className="history-list">
          {history.map((item) => (
            <div key={item.session_id} className="history-card">
              <div className="history-card__header">
                <span className="history-card__date">
                  {new Date(item.started_at).toLocaleDateString()} at{' '}
                  {new Date(item.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
                {item.urgency_level && <UrgencyBadge level={item.urgency_level} />}
              </div>
              <p className="history-card__complaint">
                {item.primary_complaint || 'Triage session'}
              </p>
              <div className="history-card__footer">
                <span className={`history-card__status ${
                  item.status === 'IN_PROGRESS' ? 'history-card__status--in-progress' :
                  item.status === 'COMPLETED' ? 'history-card__status--completed' : ''
                }`}>
                  {item.status === 'IN_PROGRESS' ? 'In Progress' :
                   item.status === 'COMPLETED' ? 'Completed' :
                   item.status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </span>
                <Link to={`/triage/${item.session_id}/status`} className="history-card__link">
                  View Details
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
