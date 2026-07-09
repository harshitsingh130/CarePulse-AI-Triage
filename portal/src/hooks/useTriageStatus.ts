/**
 * Hook for polling triage status with auto-refresh.
 */

import { useCallback, useEffect, useState } from 'react';
import type { TriageStatusResponse } from '@/types';
import { getTriageStatus } from '@/services/api';

export function useTriageStatus(sessionId: string | null, pollInterval = 5000) {
  const [status, setStatus] = useState<TriageStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    if (!sessionId) return;
    try {
      const data = await getTriageStatus(sessionId);
      setStatus(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch status');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchStatus();

    // Poll while not in terminal state
    const interval = setInterval(() => {
      if (status?.status === 'COMPLETED' || status?.status === 'ESCALATED') {
        clearInterval(interval);
        return;
      }
      fetchStatus();
    }, pollInterval);

    return () => clearInterval(interval);
  }, [fetchStatus, pollInterval, status?.status]);

  return { status, loading, error, refetch: fetchStatus };
}
