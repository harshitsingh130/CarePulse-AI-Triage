/**
 * REST API client for the Patient Portal.
 * All calls go through API Gateway with Cognito JWT authentication.
 */

import type { Appointment, ConsentStatus, TriageHistoryItem, TriageStatusResponse } from '@/types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = sessionStorage.getItem('accessToken');

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (response.status === 401) {
    // Token expired — trigger re-auth
    sessionStorage.removeItem('accessToken');
    window.location.href = '/auth';
    throw new ApiError(401, 'Authentication required');
  }

  if (!response.ok) {
    const errorText = await response.text();
    throw new ApiError(response.status, errorText);
  }

  return response.json();
}

// --- Triage ---

export async function getTriageStatus(sessionId: string): Promise<TriageStatusResponse> {
  return request<TriageStatusResponse>(`/triage/status/${sessionId}`);
}

export async function getTriageHistory(): Promise<TriageHistoryItem[]> {
  return request<TriageHistoryItem[]>('/triage/history');
}

export async function startTriage(): Promise<{ session_id: string }> {
  return request<{ session_id: string }>('/triage/start', { method: 'POST' });
}

// --- Appointments ---

export async function getAppointments(): Promise<Appointment[]> {
  return request<Appointment[]>('/appointments');
}

export async function rescheduleAppointment(appointmentId: string, newDateTime: string): Promise<{ message: string; previousTime: string; newTime: string }> {
  return request('/appointments/reschedule', {
    method: 'POST',
    body: JSON.stringify({ appointmentId, newDateTime }),
  });
}

// --- Consent ---

export async function getConsentStatus(): Promise<ConsentStatus> {
  return request<ConsentStatus>('/profile');
}

export async function grantConsent(types: string[]): Promise<void> {
  await request('/consent', {
    method: 'POST',
    body: JSON.stringify({ consent_types: types }),
  });
}

export async function revokeConsent(type: string): Promise<void> {
  await request(`/consent/${type}`, { method: 'DELETE' });
}
